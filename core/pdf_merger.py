"""
PDF Merger: Combine multiple PDFs into a single file.
"""

from typing import List
from pathlib import Path
from pypdf import PdfWriter
from rich.console import Console

console = Console()


def merge_pdfs(pdf_paths: List[str], output_path: str) -> bool:
    """
    Merge multiple PDFs into a single file.
    
    Args:
        pdf_paths: List of paths to source PDFs (in order)
        output_path: Path to save the merged PDF
        
    Returns:
        True if successful, False otherwise
    """
    if not pdf_paths:
        return False
        
    try:
        merger = PdfWriter()
        
        for pdf in pdf_paths:
            merger.append(pdf)
            
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        merger.write(output_path)
        merger.close()
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to merge PDFs: {e}")
        return False
