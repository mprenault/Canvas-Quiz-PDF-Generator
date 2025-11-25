"""
HTML Generator: Map student answers to HTML templates.

Takes HTML templates and student data, then:
1. Hides all question versions except the one the student received
2. Replaces answer placeholders with student's HTML
"""

from bs4 import BeautifulSoup, Tag
from pathlib import Path
from typing import Dict
from .latex_converter import sanitize_student_answer


def load_template(template_path: str) -> str:
    """Load HTML template from file."""
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def sanitize_filename(name: str) -> str:
    """
    Convert student name to safe filename.
    
    Examples:
        "Alice Smith" → "Alice_Smith"
        "O'Brien, John" → "OBrien_John"
    """
    # Remove special characters, replace spaces with underscores
    name = re.sub(r'[^\w\s-]', '', name)
    name = name.replace(' ', '_')
    return name


def hide_other_variants(html: str, variant_to_show: int) -> str:
    """
    Hide all question variants except the specified one.
    
    Args:
        html: Full HTML template with all variants
        variant_to_show: Variant number to display (1-12)
        
    Returns:
        Modified HTML with only student's variant
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find all question-version divs
    variant_divs = soup.find_all('div', class_='question-version')
    
    # Find the one to keep
    variant_to_keep = None
    for div in variant_divs:
        version = div.get('data-version', '')
        if version == str(variant_to_show):
            variant_to_keep = div
            break
    
    # Remove all variant divs
    for div in variant_divs:
        try:
            div.extract()  # Remove from tree but don't destroy
        except:
            pass
    
    # Re-add only the one we want
    if variant_to_keep and soup.body:
        soup.body.append(variant_to_keep)
    
    return str(soup)


def insert_student_answers(html: str, answers: Dict[str, str], num_parts: int = None) -> str:
    """
    Replace answer placeholders with student's HTML.
    
    Replaces: {{PART_A}}, {{PART_B}}, etc. with actual student answers
    
    Args:
        html: HTML template with placeholders
        answers: Dict mapping part letter → answer HTML
                 Example: {'a': '<p>6</p>', 'b': '<p>{s},{t}</p>'}
        num_parts: Number of parts expected (e.g., 2 for Q1, 3 for Q2)
                   If None, only processes parts present in answers dict
        
    Returns:
        HTML with answers inserted
    """
    part_letters = ['a', 'b', 'c', 'd', 'e', 'f']
    
    # Determine which parts to process
    if num_parts is not None:
        # Process all expected parts
        parts_to_process = part_letters[:num_parts]
    else:
        # Fallback: only process parts that exist in answers dict
        parts_to_process = list(answers.keys())
    
    for part_letter in parts_to_process:
        # Convert to placeholder format: {{PART_A}}, {{PART_B}}, etc.
        placeholder = f"{{{{PART_{part_letter.upper()}}}}}"
        
        # Get answer if it exists, otherwise None
        answer_html = answers.get(part_letter)
        
        # Replace placeholder with actual answer or "(No answer provided)"
        if answer_html and str(answer_html).strip():
            # Sanitize and convert LaTeX patterns
            cleaned_answer = sanitize_student_answer(answer_html)
            html = html.replace(placeholder, cleaned_answer)
        else:
            # No answer provided - replace with note
            html = html.replace(placeholder, '<p><em>(No answer provided)</em></p>')
    
    return html


def generate_student_html(
    template_html: str,
    student_data: Dict,
    group_id: str,
    page_break_mode: str = 'same-page',
    num_parts: int = None
) -> str:
    """
    Generate complete HTML for one student and one question group.
    
    Args:
        template_html: Full HTML template (all variants)
        student_data: Student dict with variant and answers
        group_id: Question group ID (e.g., 'q1')
        page_break_mode: Page break configuration ('same-page' or 'each-part')
        num_parts: Number of parts expected (e.g., 2 for Q1, 3 for Q2)
        
    Returns:
        Complete HTML ready for PDF rendering
    """
    # Get student's data for this question group
    group_data = student_data[group_id]
    variant = group_data['variant']
    answers = group_data['answers']
    
    # Hide other variants
    html = hide_other_variants(template_html, variant)
    
    # Insert student answers (pass num_parts to ensure all placeholders are replaced)
    html = insert_student_answers(html, answers, num_parts=num_parts)
    
    # Add student info header
    soup = BeautifulSoup(html, 'html.parser')
    
    # Create student info header
    info_div = soup.new_tag('div', **{
        'class': 'student-info',
        'style': 'background: #e3f2fd; padding: 1em; margin-bottom: 2em; border-radius: 5px;'
    })
    
    info_heading = soup.new_tag('h2')
    info_heading['style'] = 'margin-top: 0;'
    info_heading.string = f"Student: {student_data['name']}"
    info_div.append(info_heading)
    
    info_sisid = soup.new_tag('p')
    info_sisid['style'] = 'margin: 0;'
    info_sisid.string = f"SISID: {student_data.get('sisid', 'N/A')}"
    info_div.append(info_sisid)
    
    info_id = soup.new_tag('p')
    info_id['style'] = 'margin: 0;'
    info_id.string = f"Canvas ID: {student_data.get('id', 'N/A')}"
    info_div.append(info_id)
    
    # Insert at top of body
    body = soup.find('body')
    if body:
        body.insert(0, info_div)
    
    return str(soup)


import re  # Need to import for sanitize_filename

BLANK_TEMPLATE_CSS = """
.blank-answer-section {
    margin: 0.5em 0 1.5em 0;
    padding: 0.75em;
    border: 1px solid #999;
    background-color: #fff;
}
.blank-answer-section h3 {
    margin: 0 0 0.4em 0;
    font-size: 10pt;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.blank-answer-grid {
    display: flex;
    flex-direction: column;
    gap: 0.3em;
}
.blank-answer-line {
    border-bottom: 1px solid #c4c4c4;
    min-height: 16px;
}
"""


def _create_blank_answer_section(soup: BeautifulSoup, part_letter: str) -> Tag:
    """Build a blank answer grid for the specified part."""
    section = soup.new_tag(
        'div',
        **{
            'class': 'blank-answer-section',
            'data-part': part_letter,
        }
    )
    heading = soup.new_tag('h3')
    heading.string = f"Answer (Part {part_letter.upper()})"
    section.append(heading)

    grid = soup.new_tag('div', **{'class': 'blank-answer-grid'})
    for _ in range(10):
        line = soup.new_tag('div', **{'class': 'blank-answer-line'})
        grid.append(line)
    section.append(grid)
    return section


def _insert_blank_student_info(soup: BeautifulSoup) -> None:
    """Prepend a placeholder student info box that mirrors the real PDF."""
    body = soup.find('body')
    if not body:
        return

    info_div = soup.new_tag('div', **{
        'class': 'student-info',
        'style': 'background: #e3f2fd; padding: 1em; margin-bottom: 2em; border-radius: 5px;'
    })

    heading = soup.new_tag('h2')
    heading['style'] = 'margin-top: 0;'
    heading.string = 'Student: ____________________________'
    info_div.append(heading)

    sisid = soup.new_tag('p')
    sisid['style'] = 'margin: 0;'
    sisid.string = 'SISID: ____________________________'
    info_div.append(sisid)

    canvas_id = soup.new_tag('p')
    canvas_id['style'] = 'margin: 0;'
    canvas_id.string = 'Canvas ID: _______________________'
    info_div.append(canvas_id)

    body.insert(0, info_div)


def generate_blank_template_html(
    template_html: str,
    group: dict,
    variant_to_show: int = 1
) -> str:
    """
    Generate a blank HTML template for Gradescope based on one variant.

    Args:
        template_html: HTML that contains all variants for the group.
        group: Question group config dict.
        variant_to_show: Variant number to keep (default: 1).

    Returns:
        HTML string with only the selected variant and blank answer grids.
    """
    html = hide_other_variants(template_html, variant_to_show)
    soup = BeautifulSoup(html, 'html.parser')

    # Remove solution blockquotes to keep only question text
    for blockquote in soup.find_all('blockquote'):
        blockquote.decompose()

    # Replace student-answer sections with blank grids
    for section in soup.find_all('div', class_='student-answer-section'):
        part_letter = section.get('data-part', 'a')
        blank_section = _create_blank_answer_section(soup, part_letter)
        section.replace_with(blank_section)

    # Attach blank template styles
    if soup.head:
        style_tag = soup.new_tag('style')
        style_tag.string = BLANK_TEMPLATE_CSS
        soup.head.append(style_tag)

    # Add placeholder student info block
    _insert_blank_student_info(soup)

    return str(soup)

