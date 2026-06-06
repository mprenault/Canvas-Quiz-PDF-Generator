"""
Orchestrator: Main workflow that ties all modules together.

Coordinates:
1. Template generation (or loading)
2. CSV parsing
3. HTML generation per student
4. PDF rendering
"""

import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.live import Live
from .rubric_converter import convert_rubric_to_templates, save_templates
from .csv_parser import CanvasCSVParser
from .html_generator import (
    generate_student_html,
    load_template,
    sanitize_filename,
    generate_blank_template_html
)
from .pdf_generator import generate_pdf
from .zip_creator import create_quiz_zip
from .pdf_merger import merge_pdfs

console = Console()


def _split_pdfs_for_merge(
    pdf_list: List[str],
    exclude_students: Optional[List[str]],
    expected_pages: Optional[int],
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Partition a list of per-student PDF paths into a main list and an overflow list.

    A PDF lands in overflow when either:
      - its filename matches an explicitly excluded student name, or
      - its page count exceeds expected_pages (Option 2 auto-detection).

    Args:
        pdf_list: Sorted list of PDF file paths to examine.
        exclude_students: Raw student names to exclude (partial, case-insensitive).
        expected_pages: Maximum allowed pages per PDF (None = skip check).

    Returns:
        (main_list, overflow_list, excluded_by_name, overflow_by_pages)
    """
    from pypdf import PdfReader

    main_list: List[str] = []
    overflow_list: List[str] = []
    excluded_by_name: List[str] = []
    overflow_by_pages: List[str] = []

    for pdf_path in pdf_list:
        filename = Path(pdf_path).name

        # --- explicit name exclusion ---
        matched_name: Optional[str] = None
        if exclude_students:
            for raw_name in exclude_students:
                safe = sanitize_filename(raw_name)
                # Case-insensitive partial match against the sanitized name segment
                if f"_nf_{safe}".lower() in filename.lower():
                    matched_name = raw_name
                    break

        if matched_name:
            overflow_list.append(pdf_path)
            excluded_by_name.append(f"{filename} (excluded: '{matched_name}')")
            continue

        # --- page-count overflow detection ---
        if expected_pages is not None:
            try:
                page_count = len(PdfReader(pdf_path).pages)
                if page_count > expected_pages:
                    overflow_list.append(pdf_path)
                    overflow_by_pages.append(
                        f"{filename} ({page_count} pages, expected ≤{expected_pages})"
                    )
                    continue
            except Exception:
                pass  # unreadable PDF stays in main list

        main_list.append(pdf_path)

    return main_list, overflow_list, excluded_by_name, overflow_by_pages


def load_or_generate_templates(config: dict, force_regenerate: bool = False) -> Dict[str, str]:
    """
    Load existing templates or generate new ones from rubric.
    
    Args:
        config: Quiz configuration
        force_regenerate: If True, regenerate even if templates exist
        
    Returns:
        Dict mapping group_id → HTML template
    """
    quiz_id = config['quiz_id']
    templates_dir = Path(f"templates/quiz{quiz_id}")
    
    templates = {}
    all_exist = True
    
    # Check if templates already exist
    for group in config['question_groups']:
        template_file = templates_dir / f"{group['id']}_template.html"
        if not template_file.exists():
            all_exist = False
            break
    
    # Generate if needed
    if not all_exist or force_regenerate:
        console.print("[cyan]📝 Generating templates from rubric...[/cyan]")
        templates = convert_rubric_to_templates(config)
        save_templates(templates, quiz_id)
    else:
        # Load existing templates
        console.print(f"[cyan]📂 Loading existing templates from {templates_dir}/[/cyan]")
        for group in config['question_groups']:
            template_file = templates_dir / f"{group['id']}_template.html"
            templates[group['id']] = load_template(str(template_file))
            console.print(f"   [green]✓[/green] Loaded {group['id']}_template.html")
    
    return templates


async def generate_blank_templates(config: dict, templates: Dict[str, str]) -> None:
    """Create Gradescope-ready blank HTML and PDF templates per question."""
    quiz_id = config['quiz_id']
    template_html_root = Path(f"output/quiz{quiz_id}/templates/html")
    template_pdf_root = Path(f"output/quiz{quiz_id}/templates/pdf")
    template_html_root.mkdir(parents=True, exist_ok=True)
    template_pdf_root.mkdir(parents=True, exist_ok=True)

    template_images_src = Path(f"templates/quiz{quiz_id}/images")
    template_images_root = template_html_root / "images"
    if template_images_src.exists():
        if template_images_root.exists():
            shutil.rmtree(template_images_root)
        shutil.copytree(template_images_src, template_images_root)
        console.print(f"   [green]✓[/green] Copied template images to {template_images_root}/")
    else:
        console.print(f"   [yellow]⚠[/yellow] Missing template images at {template_images_src}")

    for group in config['question_groups']:
        group_id = group['id']
        console.print(f"\n[cyan]📄 Generating blank template for {group_id}[/cyan]")
        blank_html = generate_blank_template_html(
            templates[group_id],
            group,
            variant_to_show=group.get('template_variant', 1)
        )

        group_html_dir = template_html_root / group_id
        group_html_dir.mkdir(parents=True, exist_ok=True)

        group_images_dir = group_html_dir / "images"
        if template_images_src.exists():
            if group_images_dir.exists():
                shutil.rmtree(group_images_dir)
            shutil.copytree(template_images_src, group_images_dir)

        html_path = group_html_dir / f"{group_id}_blank_template.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(blank_html)

        pdf_path = template_pdf_root / f"{group_id}_blank_template.pdf"
        success = await generate_pdf(blank_html, str(pdf_path), str(html_path))

        if success:
            console.print(f"   [green]✓[/green] Blank PDF ready: {pdf_path}")
        else:
            console.print(f"   [red]✗[/red] Failed to render blank PDF for {group_id}")


async def process_quiz(
    csv_path: Optional[str],
    config: dict,
    limit: Optional[int] = None,
    student_name: Optional[str] = None,
    question_number: Optional[int] = None,
    skip_zip: bool = False,
    force_regenerate: bool = False,
    templates_only: bool = False,
    generate_templates: bool = True,
    jobs: int = 2,
    skip_merge: bool = False,
    merge_only: bool = False,
    email_mapping: Optional[Dict[str, str]] = None,
    exclude_students: Optional[List[str]] = None,
) -> None:
    """
    Main workflow: CSV → HTML → PDFs

    Args:
        csv_path: Path to Canvas CSV export (optional when templates_only)
        config: Quiz configuration dict
        limit: Optional limit on number of students (for testing)
        student_name: Optional student name filter (case-insensitive, partial match)
        question_number: Optional question number to filter (e.g. 1 for q1)
        skip_zip: If True, skip creating zip file at the end
        force_regenerate: Force regeneration of templates
        templates_only: If True, only produce blank templates
        generate_templates: If False, skip blank template generation
        jobs: Number of parallel jobs (default: 2)
        skip_merge: If True, skip merging PDFs
        merge_only: If True, skip generation and only merge existing PDFs
        email_mapping: Optional dict mapping SIS User ID -> Email
        exclude_students: Student names to exclude from the main merged PDF.
            Excluded students are placed in a separate overflow PDF instead.
            Supports partial, case-insensitive matching against sanitized filenames.
    """
    quiz_id = config['quiz_id']
    quiz_name = config['quiz_name']
    
    # Display header
    header_text = f"[bold cyan]Canvas Quiz PDF Generator[/bold cyan]\n[yellow]Quiz {quiz_id}: {quiz_name}[/yellow]"
    console.print(Panel(header_text, border_style="cyan", padding=(1, 2)))
    
    # Filter question groups if specific question requested
    if question_number is not None:
        target_id = f"q{question_number}"
        original_groups = config['question_groups']
        config['question_groups'] = [
            g for g in original_groups 
            if g['id'] == target_id
        ]
        
        if not config['question_groups']:
            console.print(f"[red]✗[/red] Error: Question 'q{question_number}' not found in config")
            console.print(f"   [dim]Available questions: {', '.join([g['id'] for g in original_groups])}[/dim]")
            return
        
        console.print(f"[cyan]ℹ Filtering for question: {target_id}[/cyan]")
    
    if merge_only:
        console.print(f"\n[bold yellow]⏭ MERGE ONLY MODE: Skipping HTML/PDF generation[/bold yellow]")
        # Skip to merging step
    else:
        # Step 1: Load or generate templates
        templates = load_or_generate_templates(config, force_regenerate)

    if generate_templates and not merge_only:
        await generate_blank_templates(config, templates)
    else:
        console.print(f"[dim]⏭ Skipping blank template generation (--no-templates)[/dim]")

    if templates_only:
        console.print(f"\n[dim]⏭ Templates-only mode: skipping student PDFs[/dim]")
        return

    if csv_path is None and not merge_only:
        console.print("[red]✗[/red] CSV path is required to generate student files")
        return

    if not merge_only:
        # Step 2: Parse CSV
        console.print(f"\n[cyan]📊 Parsing CSV...[/cyan]")
        parser = CanvasCSVParser(csv_path, config, email_mapping=email_mapping)
        all_students = parser.get_student_data(limit=None)  # Get all students first
        
        # Filter by student name if provided
        if student_name:
            if limit:
                console.print(f"   [yellow]⚠[/yellow] Note: --limit ignored when using --student filter")
            search_name = student_name.lower().strip()
            students = [
                s for s in all_students 
                if search_name in s['name'].lower()
            ]
            if not students:
                console.print(f"\n[red]✗[/red] Error: No students found matching '{student_name}'")
                console.print(f"   [dim]Available students: {', '.join([s['name'] for s in all_students[:10]])}...[/dim]")
                return
            console.print(f"   [green]✓[/green] Found {len(students)} student(s) matching '{student_name}'")
            if len(students) > 1:
                console.print(f"   [yellow]⚠[/yellow] Multiple matches: {', '.join([s['name'] for s in students])}")
        else:
            students = all_students
            if limit:
                students = students[:limit]
                console.print(f"   [yellow]⚠ Limited to {limit} students for testing[/yellow]")
        
        # Copy images to output folder for each question group
        console.print(f"\n[cyan]📁 Setting up output directories...[/cyan]")
        for group in config['question_groups']:
            group_id = group['id']
            group_name = group['name']
            base_dir = f"output/quiz{quiz_id}/{group_id}_{group_name.lower().replace(' ', '_')}"
            
            # Copy images from templates to output
            template_images = Path(f"templates/quiz{quiz_id}/images")
            output_images = Path(f"{base_dir}/html/images")
            
            if template_images.exists():
                if output_images.exists():
                    shutil.rmtree(output_images)
                shutil.copytree(template_images, output_images)
                console.print(f"   [green]✓[/green] Copied images to {base_dir}/html/images/")
        
        # Step 3: Generate PDFs for each student with progress bar
        total_pdfs = len(students) * len(config['question_groups'])
        console.print(f"\n[cyan]📄 Generating {total_pdfs} PDFs[/cyan] [dim]({len(students)} students × {len(config['question_groups'])} questions)[/dim]")
        
        pdf_count = 0
        student_times = []
        import time
        overall_start = time.time()
        
        # Split progress into two parts for cleaner UI
        # 1. Worker status (minimal: spinner + text)
        worker_progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            console=console
        )
        
        # 2. Overall progress (detailed: bar, time, counts)
        overall_progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console
        )
        
        # Group them: Workers first, then Overall at bottom
        progress_group = Group(
            worker_progress,
            overall_progress
        )
        
        # Track generated PDFs for merging: group_id -> list of paths (in order)
        generated_pdfs = {g['id']: [None] * len(students) for g in config['question_groups']}
        
        # Queue for students
        student_queue = asyncio.Queue()
        for i, student in enumerate(students, 1):
            student_queue.put_nowait((i, student))
            
        async def worker(worker_id: int, worker_task_id):
            nonlocal pdf_count
            while not student_queue.empty():
                try:
                    student_idx, student = student_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                
                # Update worker status
                worker_progress.update(worker_task_id, description=f"[cyan]Worker {worker_id}:[/cyan] Processing {student['name']}")
                
                student_start = time.time()
                student_pdf_count = 0
                
                for group in config['question_groups']:
                    group_id = group['id']
                    group_name = group['name']
                    
                    # Generate HTML for this student + question
                    #page_break_mode = group.get('page_break', 'same-page')
                    num_parts = group.get('num_parts')
                    html = generate_student_html(
                        templates[group_id],
                        student,
                        group_id,
                        #page_break_mode=page_break_mode,
                        num_parts=num_parts
                    )
                    
                    # Create output paths
                    safe_name = sanitize_filename(student['name'])
                    variant = student[group_id]['variant']
                        
                    base_dir = f"output/quiz{quiz_id}/{group_id}_{group_name.lower().replace(' ', '_')}"
                    html_dir = f"{base_dir}/html"
                    pdf_dir = f"{base_dir}/pdf"
                    
                    variant_filename = f"{group_id}v{variant:02d}_nf_{safe_name}"
                    html_path = f"{html_dir}/{variant_filename}.html"
                    pdf_path = f"{pdf_dir}/{variant_filename}.pdf"
                    
                    # Save HTML file
                    Path(html_dir).mkdir(parents=True, exist_ok=True)
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html)
                    
                    # Render to PDF
                    success = await generate_pdf(html, pdf_path, html_path, group['expected_pages'])
                    
                    if success:
                        student_pdf_count += 1
                        # Store path for merging (using index to preserve order)
                        generated_pdfs[group_id][student_idx - 1] = str(pdf_path)
                
                # Track timing
                student_elapsed = time.time() - student_start
                student_times.append(student_elapsed)
                
                # Update totals
                pdf_count += student_pdf_count
                overall_progress.advance(main_task_id)
                student_queue.task_done()
                
                # Reset worker status
                worker_progress.update(worker_task_id, description=f"[dim]Worker {worker_id}: Idle[/dim]")

        with Live(progress_group, console=console, refresh_per_second=10):
            main_task_id = overall_progress.add_task(
                "[bold cyan]Overall Progress[/bold cyan]", 
                total=len(students)
            )
            
            # Create worker tasks
            worker_tasks = []
            for i in range(jobs):
                worker_task_id = worker_progress.add_task(f"[dim]Worker {i+1}: Idle[/dim]", total=None)
                worker_tasks.append(asyncio.create_task(worker(i+1, worker_task_id)))
            
            await asyncio.gather(*worker_tasks)
    
    # Summary with timing statistics
    console.print()
    if not merge_only:
        total_time = time.time() - overall_start
        avg_time = sum(student_times) / len(student_times) if student_times else 0
        min_time = min(student_times) if student_times else 0
        max_time = max(student_times) if student_times else 0
        
        summary_text = f"""[bold cyan]Summary:[/bold cyan]
      PDFs generated: [green]{pdf_count}[/green]/[cyan]{total_pdfs}[/cyan]
      Output directory: [yellow]output/quiz{quiz_id}/[/yellow]
      
      [bold cyan]Timing:[/bold cyan]
      Total: [green]{total_time:.1f}s[/green] ({total_time/60:.1f}m)
      Avg per student: [green]{avg_time:.1f}s[/green]
      Range: [green]{min_time:.1f}s[/green] - [yellow]{max_time:.1f}s[/yellow]"""

        for i, group in enumerate(config['question_groups']):
            prefix = "└──" if i == len(config['question_groups']) - 1 else "├──"
            group_dir = f"{group['id']}_{group['name'].lower().replace(' ', '_')}"
            summary_text += f"\n  [dim]{prefix} {group_dir}/[/dim]"
            summary_text += f"\n  [dim]    ├── html/ ({len(students)} files)[/dim]"
            summary_text += f"\n  [dim]    └── pdf/ ({len(students)} files)[/dim]"
        
        console.print(Panel(summary_text, border_style="green", padding=(1, 2)))
    
    # Step 4: Merge PDFs
    if not skip_merge:
        console.print(f"\n[cyan]📑 Merging PDFs...[/cyan]")
        for group in config['question_groups']:
            group_id = group['id']
            group_name = group['name']
            base_dir = f"output/quiz{quiz_id}/{group_id}_{group_name.lower().replace(' ', '_')}"
            expected_pages: Optional[int] = group.get('expected_pages')

            pdf_list = []
            if merge_only:
                pdf_dir = Path(f"{base_dir}/pdf")
                if pdf_dir.exists():
                    pdf_list = sorted([
                        str(p) for p in pdf_dir.glob("*.pdf")
                        if not p.name.endswith("_merged.pdf")
                        and not p.name.endswith("_overflow_merged.pdf")
                    ])
            else:
                pdf_list = sorted([p for p in generated_pdfs[group_id] if p is not None])

            if not pdf_list:
                console.print(f"   [yellow]⚠[/yellow] No PDFs to merge for {group_id}")
                continue

            main_list, overflow_list, excluded_by_name, overflow_by_pages = _split_pdfs_for_merge(
                pdf_list, exclude_students, expected_pages
            )

            # Report exclusions / overflows before merging
            for label in excluded_by_name:
                console.print(f"   [yellow]⚠[/yellow] Excluded (name match): {label}")
            for label in overflow_by_pages:
                console.print(f"   [yellow]⚠[/yellow] Overflow (page count): {label}")

            # Main merged PDF
            if main_list:
                merged_path = f"{base_dir}/{group_id}_merged.pdf"
                if merge_pdfs(main_list, merged_path):
                    console.print(
                        f"   [green]✓[/green] Merged {len(main_list)} PDFs → {merged_path}"
                    )
            else:
                console.print(f"   [yellow]⚠[/yellow] No PDFs in main list for {group_id} after filtering")

            # Overflow merged PDF (excluded + page-count violators)
            if overflow_list:
                overflow_path = f"{base_dir}/{group_id}_overflow_merged.pdf"
                if merge_pdfs(overflow_list, overflow_path):
                    console.print(
                        f"   [cyan]📎[/cyan] Overflow PDF ({len(overflow_list)} student(s)) → {overflow_path}"
                    )
    else:
        console.print(f"\n[dim]⏭ Skipping PDF merge (--no-merge)[/dim]")

    # Create zip file automatically (unless skipped)
    if not skip_zip:
        console.print(f"\n[cyan]📦 Creating zip file...[/cyan]")
        zip_success = create_quiz_zip(quiz_id)
        if zip_success:
            zip_path = Path(f"output/quiz{quiz_id}pdfs.zip")
            if zip_path.exists():
                zip_size = zip_path.stat().st_size / (1024 * 1024)  # MB
                console.print(f"   [green]✓[/green] Created: {zip_path}")
                console.print(f"   [dim]Size: {zip_size:.1f} MB[/dim]")
        else:
            console.print(f"   [yellow]⚠[/yellow] Warning: Could not create zip file")
    else:
        console.print(f"\n[dim]⏭ Skipping zip file creation (--no-zip)[/dim]")

