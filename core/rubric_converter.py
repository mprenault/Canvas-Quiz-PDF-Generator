"""
Rubric Converter: Convert LaTeX rubrics to HTML templates.
Assumes:
- Rubric folder contains .tex file and all image files
  - Images are referenced in LaTeX with \\includegraphics{filename.png}
- Course staff unzips materials directly into rubrics/quizX/
"""

# ==================== DEBUG FLAG ====================
DEBUG = True   # ← Set to True for detailed debugging output (including all loops)
# ====================================================

import subprocess
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, Tuple


def debug_print(*args, **kwargs):
    """Print debug messages only if DEBUG is enabled."""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)


def find_rubric_file(rubric_folder: str) -> Path:
    """Find the main rubric .tex file in the folder."""
    debug_print(f"Searching for rubric file in: rubrics/{rubric_folder}")
    folder = Path(f"rubrics/{rubric_folder}")
   
    candidates = list(folder.glob("*_solutions_rubric.tex"))
    debug_print(f"  → Solutions rubric candidates: {len(candidates)}")
    
    if not candidates:
        candidates = list(folder.glob("*_rubric.tex"))
        debug_print(f"  → Regular rubric candidates: {len(candidates)}")
   
    if not candidates:
        raise FileNotFoundError(f"No rubric .tex file found in {folder}")
   
    debug_print(f"✓ Selected rubric: {candidates[0].name}")
    return candidates[0]


def copy_images_to_templates(rubric_folder: str, quiz_id: int) -> None:
    """Copy all image files from rubrics/quizX/ to templates/quizX/images/"""
    source_dir = Path(f"rubrics/{rubric_folder}")
    dest_dir = Path(f"templates/quiz{quiz_id}/images")
    debug_print(f"Starting image copy: {source_dir} → {dest_dir}")
    
    dest_dir.mkdir(parents=True, exist_ok=True)
   
    image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.svg', '*.gif']
    copied = 0
   
    debug_print(f"Processing {len(image_extensions)} image extension patterns...")
    for i, pattern in enumerate(image_extensions, 1):
        debug_print(f"  [Image Pattern Loop {i}/{len(image_extensions)}] Pattern: {pattern}")
        for img_file in source_dir.glob(pattern):
            dest_file = dest_dir / img_file.name
            shutil.copy2(img_file, dest_file)
            debug_print(f"    → Copied: {img_file.name} ({img_file.stat().st_size:,} bytes)")
            copied += 1
   
    debug_print(f"Image copy complete. Total files copied: {copied}")
    print(f" ✓ Copied {copied} image files")


def extract_latex_section(tex_file: Path, line_range: Tuple[int, int]) -> str:
    """Extract specific line range from LaTeX file."""
    debug_print(f"Extracting lines {line_range[0]}-{line_range[1]} from {tex_file.name}")
    
    with open(tex_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
   
    start, end = line_range
    content = ''.join(lines[start-1:end])
    debug_print(f"  → Extracted {len(content):,} characters ({end - start + 1} lines)")
    return content


def replace_tikz_with_images(latex_content: str, image_map: dict) -> str:
    """Replace TikZ code with includegraphics based on version mapping."""
    if not image_map:
        debug_print("No image_map provided, skipping TikZ replacement")
        return latex_content
   
    debug_print(f"Starting TikZ replacement with map: {list(image_map.keys())}")
    
    tikz_pattern = r'\\begin\{figure\}\[H\].*?\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}.*?\\end\{figure\}'
    version_num = 1

    def replace_with_image(match):
        nonlocal version_num
        debug_print(f"  [TikZ Replace Loop] Processing figure #{version_num}")
        if version_num in image_map:
            img_file = image_map[version_num]
            debug_print(f"    → Replacing with: {img_file}")
            replacement = f'\\begin{{figure}}[H]\n\\centering\n\\includegraphics[width=0.8\\textwidth]{{{img_file}}}\n\\end{{figure}}'
            version_num += 1
            return replacement
        else:
            debug_print(f"    → No mapping for version {version_num}, keeping original")
            version_num += 1
            return match.group(0)

    result = re.sub(tikz_pattern, replace_with_image, latex_content, flags=re.DOTALL)
    debug_print(f"TikZ replacement complete. Processed {version_num-1} figures.")
    return result


def preprocess_exam_latex(latex_content: str, image_map: dict = None) -> str:
    """Convert exam class environments to standard LaTeX for Pandoc."""
    debug_print("Starting LaTeX preprocessing...")
    
    if image_map:
        latex_content = replace_tikz_with_images(latex_content, image_map)
   
    # Remove environment markers
    for env in ['questions', 'parts']:
        before = len(latex_content)
        latex_content = latex_content.replace(f'\\begin{{{env}}}', '')
        latex_content = latex_content.replace(f'\\end{{{env}}}', '')
        debug_print(f"  Removed \\{env} environments | chars removed: {before - len(latex_content)}")
   
    # Convert question and part commands
    latex_content = re.sub(
        r'\\question\[(\d+)\]',
        r'\\section*{Question}',
        latex_content
    )
    latex_content = re.sub(
        r'\\question',
        r'\\section*{Question}',
        latex_content
    )
    latex_content = re.sub(
        r'\\part\[(\d+)\]\s*',
        r'\\subsection*{Part}',
        latex_content
    )
    latex_content = re.sub(
        r'\\part\s*',
        r'\\subsection*{Part}',
        latex_content
    )

   
    # Convert solutionbox
    latex_content = re.sub(
        r'\\begin\{solutionbox\}\{.*\}+',
        r'\\begin{quote}\\textbf{Solution:}',
        latex_content
    )
    latex_content = re.sub(
        r'\\end\{solutionbox\}',
        r'\\end{quote}',
        latex_content
    )

    # Convert choices
    latex_content = re.sub(
        r'\\begin\{choices\}',
        r'\\begin{enumerate}',
        latex_content
    )
    latex_content = re.sub(
        r'\\begin\{oneparchoices\}',
        r'\\begin{enumerate}',
        latex_content
    )    
    latex_content = re.sub(
        r'\\end\{choices\}',
        r'\\end{enumerate}\\begin{quote}\\end{quote}',
        latex_content
    )
    latex_content = re.sub(
        r'\\end\{itemize\}',
        r'\\end{itemize}\\begin{quote}\\end{quote}',
        latex_content
    )
    latex_content = re.sub(
        r'\\end\{oneparchoices\}',
        r'\\end{enumerate}\\begin{quote}\\end{quote}',
        latex_content
    )
    latex_content = re.sub(
        r'\\CorrectChoice(.*)',
        r'\\item CORRECT: \1',
        latex_content
    )
    latex_content = re.sub(
        r'\\choice(.*)',
        r'\\item\1',
        latex_content
    )
   
    debug_print("Preprocessing completed")
    return latex_content


def latex_to_html_pandoc(latex_content: str, group_id: str) -> str:
    """Convert LaTeX to HTML using Pandoc."""
    debug_print(f"Starting Pandoc conversion for group: {group_id}")
    
    full_latex = f"""\\documentclass{{article}}
\\usepackage{{amsmath}}
\\usepackage{{amsfonts}}
\\usepackage{{amsthm}}
\\usepackage{{graphicx}}
\\begin{{document}}
{latex_content}
\\end{{document}}
"""
   
    temp_tex = Path(f"temp_{group_id}.tex")
    temp_html = Path(f"temp_{group_id}.html")
   
    try:
        with open(temp_tex, 'w', encoding='utf-8') as f:
            f.write(full_latex)
        debug_print(f"  Created temporary TeX file: {temp_tex}")
       
        result = subprocess.run([
            'pandoc',
            str(temp_tex),
            '-o', str(temp_html),
            '--standalone',
#            '--mathjax=https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js', 
            '--mathml',  #MathML doesn't add the polyfill.ip
            '--from=latex',
            '--to=html5',
            '--css=https://cdn.jsdelivr.net/npm/water.css@2/out/water.css'
        ], capture_output=True, text=True)
       
        if result.returncode != 0:
            debug_print("Pandoc conversion FAILED")
            debug_print(f"  Error output: {result.stderr.strip()[:1000]}")
            debug_file = Path(f"debug_{group_id}.tex")
            shutil.copy2(temp_tex, debug_file)
            print(f" Saved debug file: {debug_file}")
            raise RuntimeError(f"Pandoc failed - check {debug_file}")
       
        with open(temp_html, 'r', encoding='utf-8') as f:
            html = f.read()
        
        debug_print(f"  Pandoc successful. Output size: {len(html):,} characters")
        return html
       
    finally:
        if temp_tex.exists():
            temp_tex.unlink()
        if temp_html.exists():
            temp_html.unlink()


def fix_image_paths(html: str) -> str:
    """Update image src paths to point to images/ subdirectory."""
    debug_print("Starting image path fixing loop...")
    soup = BeautifulSoup(html, 'html.parser')
    images = soup.find_all('img')
    debug_print(f"  Found {len(images)} images")
    
    updated = 0
    for i, img in enumerate(images, 1):
        src = img.get('src', '')
        debug_print(f"  [Image Path Loop {i}/{len(images)}] src='{src}'")
        if src and not src.startswith(('http://', 'https://', 'images/')):
            old_src = src
            last_slash = src.rfind('/')
            filename = src[last_slash + 1:] if last_slash != -1 else src
            img['src'] = f"images/{filename}"
            img['class'] = img.get('class', []) + ['rubric-image']
            debug_print(f"    → Updated: '{old_src}' → 'images/{filename}'")
            updated += 1
        else:
            debug_print(f"    → Skipped (path already correct)")
    
    debug_print(f"Image path fixing complete. Updated {updated} images.")
    return str(soup)


def add_question_structure_and_placeholders(html: str, group: dict) -> str:
    """Add question version wrappers and answer placeholders."""
    debug_print(f"Starting structure and placeholder addition for group {group['id']}")
    
    soup = BeautifulSoup(html, 'html.parser')
    all_h1s = soup.find_all('h1')
    sections = [h1 for h1 in all_h1s if re.search(r'Question', h1.get_text())]
    
    debug_print(f"  Found {len(sections)} question sections")
    
    # Process sections in reverse order
    for version_num in range(len(sections), 0, -1):
        idx = version_num - 1
        section = sections[idx]
        debug_print(f"  [Question Version Loop] Processing version {version_num} (index {idx})")

        
        wrapper = soup.new_tag('div', **{
            'class': 'question-version',
            'data-version': str(version_num),
            'data-group': group['id']
        })
        
        # Collect elements to wrap
        elements_to_wrap = []
        current = section
        while current:
            elements_to_wrap.append(current)
            #debug_print(f"Wrapping: {current}")
            next_elem = current.next_sibling
            if next_elem and (next_elem.name =='div' or (next_elem.name == 'h1' and re.search(r'Question', next_elem.get_text()))):
                break
            current = next_elem
        
        debug_print(f"    Collected {len(elements_to_wrap)} elements for wrapping")
        
        # Wrap elements
        parent = section.parent
        insert_position = list(parent.children).index(section) if parent else 0
        
        for elem in elements_to_wrap:
            if elem.parent:
                elem.extract()
        for elem in elements_to_wrap:
            wrapper.append(elem)
        
        if parent:
            parent.insert(insert_position, wrapper)

        #debug_print(wrapper)
        
        # Process parts
        parts = wrapper.find_all('h2', string=re.compile(r'Part'))
        debug_print(f"    Found {len(parts)} parts in version {version_num}")       
        
        part_letters = [chr(i) for i in range(ord('a'), ord('z') + 1)]

        if len(parts) == 0:
            debug_print("    No parts found → adding default Part A")
            parts = [None]

        for p_idx, part_header in enumerate(parts):
            debug_print(f"      [Part Loop {p_idx+1}/{len(parts)}] Processing part {p_idx+1}")
            if p_idx < len(part_letters):
                part_letter = part_letters[p_idx]
                
                # Update part header
                if part_header is not None:
                    original_text = part_header.get_text()
                    new_text = f"Part {part_letter.upper()}" + original_text[4:]
                    part_header.string = new_text
                    if p_idx > 0 and group['page_break'] == 'each-part-not-first':
                        part_header['class'].append('pagebreakbefore')
                    if group['page_break'] == 'each-part':
                        part_header['class'].append('pagebreakbefore')                        
                    # Add student answer section
                    solution_box = part_header.find_next('blockquote')
                else:
                    solution_box = wrapper.find('blockquote')

                if solution_box:
                    target = solution_box
                    debug_print(f"    → Found solution box for Part {part_letter.upper()}")
                else:
                    # No solution box → add at the end of the question wrapper
                    target = wrapper
                    debug_print(f"    → No solution box found, adding Part {part_letter.upper()} at end of question")
                    
                answer_section = soup.new_tag('div', **{
                    'class': 'student-answer-section',
                    'data-part': part_letter
                })
                
                h3 = soup.new_tag('h3')
                h3.string = f"Student Answer (Part {part_letter.upper()}):"
                answer_section.append(h3)
                
                placeholder = soup.new_tag('div', **{'class': 'answer-placeholder'})
                placeholder.string = f"{{{{PART_{part_letter.upper()}}}}}"
                answer_section.append(placeholder)
                
                target.insert_after(answer_section)
                debug_print(f"    → Added student answer section for Part {part_letter.upper()}")
    
    # Add CSS
    style_tag = soup.new_tag('style')
    style_tag.string = """
        @page { margin: 0.75in; }
        body { font-family: 'Computer Modern', 'Latin Modern', 'Times New Roman', serif; font-size: 11pt; line-height: 1.3; }
        .question-version { margin: 0; padding: 0; }
        .rubric-image { display: block; margin: 0.5em auto; max-width: 400px; max-height: 250px; }
        blockquote { background-color: #f0f0f0; border-left: 3px solid #666; padding: 0.4em 0.8em; }
        .student-answer-section { margin: 0.3em 0 0.6em 0; padding: 0.5em; background-color: #fffacd; border-left: 3px solid #ffa500; }
        .answer-placeholder { padding: 0.4em; background-color: white; border: 1px solid #ddd; min-height: 2em; }
        .pagebreakbefore {   break-before: page; page-break-before: always;  }
    """
    if soup.head:
        soup.head.append(style_tag)
    
    debug_print("Question structure and placeholders added successfully")
    return str(soup)


def convert_rubric_to_templates(config: dict) -> Dict[str, str]:
    """Main conversion function."""
    debug_print("=== STARTING FULL RUBRIC CONVERSION ===")
    debug_print(f"Total question groups to process: {len(config.get('question_groups', []))}")
    
    rubric_folder = config['rubric_folder']
    quiz_id = config['quiz_id']
   
    rubric_file = find_rubric_file(rubric_folder)
    print(f"\n📝 Converting rubric: {rubric_file}")
   
    copy_images_to_templates(rubric_folder, quiz_id)
   
    templates = {}
    for i, group in enumerate(config['question_groups'], 1):
        debug_print(f"\n[Main Group Loop {i}/{len(config['question_groups'])}] Processing {group['name']} ({group['id']})")
        print(f"\n Processing {group['name']} ({group['id']})...")
        
        latex_content = extract_latex_section(rubric_file, group['latex_line_range'])
        image_map = group.get('image_map', None)
        
        latex_content = preprocess_exam_latex(latex_content, image_map)
        html = latex_to_html_pandoc(latex_content, group['id'])
        html = fix_image_paths(html)
        html = add_question_structure_and_placeholders(html, group)
       
        templates[group['id']] = html
        print(f" ✓ Template complete for {group['id']}")
   
    debug_print("=== RUBRIC CONVERSION COMPLETED SUCCESSFULLY ===")
    return templates


def save_templates(templates: Dict[str, str], quiz_id: int) -> None:
    """Save templates to disk."""
    debug_print(f"Saving {len(templates)} templates for quiz {quiz_id}")
    
    output_dir = Path(f"templates/quiz{quiz_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
   
    for i, (group_id, html) in enumerate(templates.items(), 1):
        debug_print(f"  [Save Loop {i}/{len(templates)}] Saving {group_id}_template.html")
        output_file = output_dir / f"{group_id}_template.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        debug_print(f"    → Saved {len(html):,} characters")
        print(f"\n 💾 Saved: {output_file}")
    
    debug_print("All templates saved successfully")
