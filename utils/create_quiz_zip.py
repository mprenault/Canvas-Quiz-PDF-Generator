#!/usr/bin/env python3
"""
Standalone script to create a zip file of all PDFs organized by question.

Usage:
    python create_quiz_zip.py --quiz 5
    python create_quiz_zip.py --quiz 5 --output custom_name.zip
"""

import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.zip_creator import create_quiz_zip

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Create a zip file of all quiz PDFs organized by question"
    )
    parser.add_argument(
        '--quiz',
        type=int,
        required=True,
        help='Quiz number (e.g., 5)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Custom output zip filename (default: quiz{id}pdfs.zip)'
    )
    
    args = parser.parse_args()
    
    header = f"[bold cyan]Quiz PDF Zip Creator[/bold cyan]\n[yellow]Quiz {args.quiz}[/yellow]"
    console.print(Panel(header, border_style="cyan", padding=(1, 2)))
    
    # Check if output directory exists
    quiz_output_dir = Path(f"output/quiz{args.quiz}")
    if not quiz_output_dir.exists():
        console.print(f"[red]✗[/red] Error: Output directory {quiz_output_dir} does not exist")
        console.print(f"   [dim]Run the quiz generation first: python run_quiz.py --quiz {args.quiz} --csv ...[/dim]")
        exit(1)
    
    console.print(f"\n[cyan]📦 Creating zip file...[/cyan]")
    
    # Determine output zip name
    if args.output is None:
        output_name = f"quiz{args.quiz}pdfs.zip"
    else:
        output_name = args.output
    
    output_path = Path(f"output/{output_name}")
    
    # Count PDFs before creating zip
    total_pdfs = 0
    from importlib import import_module
    try:
        config_module = import_module(f'configs.quiz{args.quiz}_config')
        config = config_module.QUIZ_CONFIG
        for group in config['question_groups']:
            group_id = group['id']
            group_name = group['name']
            pdf_dir = quiz_output_dir / f"{group_id}_{group_name.lower().replace(' ', '_')}" / "pdf"
            if pdf_dir.exists():
                pdf_files = list(pdf_dir.glob("*.pdf"))
                total_pdfs += len(pdf_files)
                console.print(f"   [green]✓[/green] Found {len(pdf_files)} PDFs in {group_id}_{group_name.lower().replace(' ', '_')}/pdf/")
    except ImportError:
        console.print(f"[red]✗[/red] Error: Could not load configs/quiz{args.quiz}_config.py")
        exit(1)
    
    if total_pdfs == 0:
        console.print(f"[red]✗[/red] Error: No PDFs found to zip")
        exit(1)
    
    # Create zip
    success = create_quiz_zip(args.quiz, output_name)
    
    if success:
        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
        console.print(f"\n[green]✓[/green] Created: {output_path}")
        console.print(f"   [dim]Total PDFs: {total_pdfs}[/dim]")
        console.print(f"   [dim]Size: {file_size:.1f} MB[/dim]")
        console.print(f"\n[green]✓[/green] Done!")
    else:
        console.print(f"\n[red]✗[/red] Failed to create zip file")
        exit(1)


if __name__ == '__main__':
    main()

