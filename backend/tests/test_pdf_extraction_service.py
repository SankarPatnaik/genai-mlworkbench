import io
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.pdf_extraction_service import LayoutElement, pdf_extraction_service


def build_minimal_text_pdf() -> bytes:
    stream = b"BT\n/F1 12 Tf\n72 720 Td\n(Invoice 1001) Tj\n0 -20 Td\n(Total 42.00) Tj\nET"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    pdf = io.BytesIO()
    pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(pdf.tell())
        pdf.write(obj)
    xref = pdf.tell()
    pdf.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode())
    pdf.write(f"trailer\n<< /Root 1 0 R /Size {len(offsets)} >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return pdf.getvalue()


class PDFExtractionServiceTest(unittest.TestCase):
    def test_text_file_extraction_preserves_body(self):
        result = pdf_extraction_service.extract_document("notes.txt", b"alpha\nbeta")

        self.assertEqual(result["metadata"]["profile"], "raw_text")
        self.assertEqual(result["metadata"]["parser_chain"], ["raw-text"])
        self.assertIn("alpha\nbeta", result["text"])

    def test_layout_text_uses_horizontal_positioning(self):
        elements = [
            LayoutElement(
                page_number=1,
                type="text",
                text="left",
                bbox={"x0": 72, "top": 50, "x1": 96, "bottom": 62},
                source="test",
            ),
            LayoutElement(
                page_number=1,
                type="text",
                text="right",
                bbox={"x0": 300, "top": 51, "x1": 330, "bottom": 63},
                source="test",
            ),
        ]

        text = pdf_extraction_service._elements_to_layout_text(elements, 612)

        self.assertRegex(text, r"left\s{2,}right")

    def test_digital_pdf_extraction_has_page_marker(self):
        result = pdf_extraction_service.extract_document("invoice.pdf", build_minimal_text_pdf())

        self.assertEqual(result["metadata"]["profile"], "digital_pdf")
        self.assertIn("Invoice 1001", result["text"])
        self.assertIn("--- Page 1 ---", result["text"])


if __name__ == "__main__":
    unittest.main()
