"""
PDF Generator: Convert HTML to PDF using Playwright.

Uses headless Chromium to render HTML with MathJax support.
Critical for math-heavy content where equations need proper rendering.
"""

from playwright.async_api import async_playwright
from pypdf import PdfReader, PdfWriter, PageObject
from pathlib import Path
import asyncio


async def generate_pdf(html_content: str, output_path: str, html_file_path: str = None, exp_pages = None) -> bool:
    """
    Convert HTML to PDF using Playwright with MathJax support.
    
    Args:
        html_content: Complete HTML string (used if html_file_path is None)
        output_path: Where to save PDF
        html_file_path: Optional path to HTML file (for proper image loading)
        
    Returns:
        True if successful, False otherwise
    """
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        async with async_playwright() as p:
            # Launch headless Chrome
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            # Load HTML - use file path if provided (for proper image paths)
            if html_file_path:
                html_file_url = f"file://{Path(html_file_path).absolute()}"
                await page.goto(html_file_url, timeout=60000)
            else:
                await page.set_content(html_content, timeout=60000)
            
            await page.wait_for_load_state('networkidle')

            
            # Generate PDF
            await page.pdf(
                path=output_path,
                format='Letter',
                margin={
                    'top': '0.75in',
                    'right': '0.75in',
                    'bottom': '0.75in',
                    'left': '0.75in'
                },
                print_background=True
            )
            
            await browser.close()

            if exp_pages is not None:
                reader = PdfReader(output_path)
                writer = PdfWriter()

                for page in reader.pages:
                    writer.add_page(page)
                current_pages = len(reader.pages)
                if current_pages < exp_pages:
                    pages_to_add = exp_pages - current_pages
                    for _ in range(pages_to_add):
                        writer.add_blank_page()
                    with open(output_path, "wb") as f:
                        writer.write(f)
            
            return True
            
    except Exception as e:
        print(f"      ✗ PDF generation failed: {e}")
        return False


async def generate_pdf_batch(jobs: list) -> int:
    """
    Generate multiple PDFs in parallel using Playwright.
    
    Args:
        jobs: List of (html_content, output_path) tuples
        
    Returns:
        Number of successfully generated PDFs
    """
    tasks = [generate_pdf(html, path) for html, path in jobs]
    results = await asyncio.gather(*tasks)
    return sum(results)

