import unittest
import os
from pathlib import Path
from core.pdf_merger import merge_pdfs
from pypdf import PdfWriter, PdfReader

class TestPDFMerger(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_pdf_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.output = self.test_dir / "merged.pdf"
        
    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def _create_dummy_pdf(self, path, content_text):
        """Create a PDF with specific text content to verify order."""
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(path))
        c.drawString(100, 750, content_text)
        c.save()
        
    def test_merge_pdfs_order(self):
        """Verify that PDFs are merged in the order provided in the list."""
        # Create 3 PDFs with different variants
        pdf1 = self.test_dir / "q1v01_Alice.pdf"
        pdf2 = self.test_dir / "q1v02_Bob.pdf"
        pdf3 = self.test_dir / "q1v01_Charlie.pdf"
        
        # We need reportlab to write text content for verification
        # If reportlab is not available, we'll skip the content check and just check page count
        try:
            import reportlab
            self._create_dummy_pdf(pdf1, "Variant 1 - Alice")
            self._create_dummy_pdf(pdf2, "Variant 2 - Bob")
            self._create_dummy_pdf(pdf3, "Variant 1 - Charlie")
            has_content = True
        except ImportError:
            # Fallback for environment without reportlab
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.write(pdf1)
            writer.write(pdf2)
            writer.write(pdf3)
            writer.close()
            has_content = False

        # The orchestrator is responsible for sorting. 
        # Here we simulate what the orchestrator does: passing a SORTED list.
        # We want to verify that merge_pdfs respects the order we give it.
        
        # Simulate the orchestrator sorting: v1s first, then v2s
        # Expected order: q1v1_Alice, q1v1_Charlie, q1v2_Bob
        sorted_paths = sorted([str(pdf1), str(pdf2), str(pdf3)])
        
        success = merge_pdfs(sorted_paths, str(self.output))
        self.assertTrue(success)
        
        reader = PdfReader(str(self.output))
        self.assertEqual(len(reader.pages), 3)
        
        if has_content:
            # Verify the order of content
            page1_text = reader.pages[0].extract_text()
            page2_text = reader.pages[1].extract_text()
            page3_text = reader.pages[2].extract_text()
            
            self.assertIn("Variant 1 - Alice", page1_text)
            self.assertIn("Variant 1 - Charlie", page2_text)
            self.assertIn("Variant 2 - Bob", page3_text)

if __name__ == '__main__':
    unittest.main()
