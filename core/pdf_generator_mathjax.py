"""
PDF Generator: Convert HTML to PDF using Playwright.

Uses headless Chromium to render HTML with MathJax support.
Critical for math-heavy content where equations need proper rendering.
"""

from playwright.async_api import async_playwright
from pathlib import Path
import asyncio


async def generate_pdf(html_content: str, output_path: str, html_file_path: str = None) -> bool:
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

            # 1. Inject the tracking arrays before triggering MathJax
            await page.evaluate('''() => {
                window._mjPendingMath = []; // Stores what is currently rendering
                window._mjAllMathFound = []; // Stores all discovered items

                if (window.MathJax && window.MathJax.startup) {
                    // Intercept MathJax's document creation to listen to the render loop
                    const handler = MathJax.startup.document.menu.handler;
                    const createDoc = handler.create;

                    handler.create = function (html, options) {
                        const doc = createDoc.call(this, html, options);

                        // Hook directly into the rendering loop stages
                        doc.renderActions.add('track-start', 1, (doc) => {
                            for (const item of doc.math) {
                                const mathInfo = {
                                    text: item.math,
                                    isDisplay: item.display,
                                    outerHTML: item.start.node.parentElement ? item.start.node.parentElement.outerHTML.substring(0, 300) : 'Unknown element'
                                };
                                window._mjPendingMath.push(mathInfo);
                                window._mjAllMathFound.push(mathInfo);
                            }
                        });

                        // Hook into individual math item metrics/completion
                        doc.renderActions.add('track-end', 999, (doc) => {
                            // As math items successfully finish formatting, clear them from the pending array
                            window._mjPendingMath = [];
                        });

                        return doc;
                    };
                }
            }''')
            
            # Wait for MathJax to finish rendering
            try:
                # 1. Ensure MathJax is loaded
                await page.wait_for_function('window.MathJax !== undefined', timeout=10000)
        
                # 2. Wait until MathJax is completely done typesetting the page
                await page.evaluate('''() => {
                    return new Promise((resolve) => {
                        if (window.MathJax.startup && window.MathJax.startup.promise) {
                            window.MathJax.startup.promise.then(() => {
                                // MathJax is ready, now force-wait for any active typesetting loops
                                MathJax.typesetPromise().then(resolve);
                            });
                        } else {
                            resolve(); // Fallback if MathJax v2 or alternative config is used
                        }
                    });
                }''')

                #### OLD
                #await page.wait_for_function(
                #    'window.MathJax && window.MathJax.startup && window.MathJax.startup.promise',
                #    timeout=10000
                #)
                #await page.evaluate('MathJax.startup.promise')
                
                # Give a bit more time for complex equations
                #await page.wait_for_timeout(1000)
                #######
                
            except Exception as e:
                print(f"      ⚠ MathJax timeout (continuing anyway): {e}")

                # 3. Retrieve the tracked math telemetry if a timeout happened
                telemetry = await page.evaluate('''() => {
                    return {
                        pending: window._mjPendingMath || [],
                        total_count: window._mjAllMathFound ? window._mjAllMathFound.length : 0
                    };
                }''')

                print(f"Total equations scanned on page: {telemetry['total_count']}")
                print("--- EQUATIONS CAUSING THE TIMEOUT ---")

                if not telemetry['pending']:
                    # If the queue is technically empty, MathJax is stuck waiting on an external dependency
                    print("No pending math strings. MathJax is likely hanging on a network asset timeout (like web fonts or an external package \\require).")
                else:
                    for idx, math in enumerate(telemetry['pending'], 1):
                        print(f"\n[Stuck Equation #{idx}]")
                        print(f"LaTeX Source:  {math['text']}")
                        print(f"Display Mode:  {math['isDisplay']}")
                        print(f"Parent Element Snippet:\n  {math['outerHTML']}\n")                
            
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

