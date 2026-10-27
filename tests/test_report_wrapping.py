"""
Tests for T11 Part B5: PDF and Excel Text Wrapping Verification.
Uses pdfplumber to verify generated tables don't exceed printable width or cell bounds
for wide names, long aliases (120+ chars), and entities like Aeroflot, HAMAS, and Volga-Dnepr.
"""

from pathlib import Path
import unittest
import openpyxl
import pdfplumber

from modules.reporting.generator import generate_reports

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestReportWrapping(unittest.TestCase):
    def test_01_pdf_table_bounds_and_wrapping(self):
        long_alias = "VERY LONG ALIAS " + "ACME-INTERNATIONAL-TRANSLITERATION-AND-EXPORT-LOGISTICS-SUBSIDIARY-" * 2
        test_hits = [
            {
                "source_list": "us_csl",
                "source_id": "CSL-AERO-001/2026",
                "tier": "POTENTIAL_MATCH",
                "primary_name": "Public Joint Stock Company Aeroflot - Russian Airlines",
                "matched_name": "PJSC Aeroflot",
                "expanded_from": "Aeroflot",
                "score": 0.9850,
                "reason": "name_exact_match",
            },
            {
                "source_list": "us_ofac",
                "source_id": "18715",
                "tier": "POTENTIAL_MATCH",
                "primary_name": "HAMAS",
                "matched_name": "HARAKAT AL-MUQAWAMA AL-ISLAMIYA",
                "expanded_from": long_alias,
                "score": 0.9500,
                "reason": "name_alias_match",
            },
            {
                "source_list": "uk_csl",
                "source_id": "RUS0250",
                "tier": "POTENTIAL_MATCH",
                "primary_name": "Volga-Dnepr Airlines LLC / Volga Logistics Freight Forwarding Joint Venture",
                "matched_name": "Volga Logistics",
                "score": 0.9100,
                "reason": "name_substring_match",
            },
        ]

        pdf_path, excel_path = generate_reports(
            search_type="Organisation",
            inputs={"name": "Aeroflot / HAMAS / Volga Logistics Test"},
            overall_banner="🔴 POTENTIAL MATCH — Review required under Sanctions Compliance Policy",
            source_statuses=[{"id": "us_ofac", "tier": "POTENTIAL_MATCH", "status": "OK", "below_count": 0}],
            sanctions_hits=test_hits,
            aviation_hits=[],
            country_risk_hits=[],
        )

        try:
            # 1. Verify PDF with pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                self.assertGreater(len(pdf.pages), 0)
                for page_idx, page in enumerate(pdf.pages):
                    # Printable width for A4 (595.27 pt width, 36pt margins -> max x1 = 595.27 - 36 = 559.27)
                    max_printable_x = 560.0
                    min_printable_x = 35.0

                    words = page.extract_words()
                    for w in words:
                        self.assertLessEqual(
                            w["x1"],
                            max_printable_x + 5.0,
                            f"Word '{w['text']}' on page {page_idx+1} overflows right margin (x1={w['x1']:.1f})"
                        )
                        self.assertGreaterEqual(
                            w["x0"],
                            min_printable_x - 5.0,
                            f"Word '{w['text']}' on page {page_idx+1} underflows left margin (x0={w['x0']:.1f})"
                        )

            # 2. Verify Excel with openpyxl
            wb = openpyxl.load_workbook(excel_path)
            ws_sanc = wb["Candidates & Findings"]
            self.assertIsNotNone(ws_sanc)
            for row in ws_sanc.iter_rows(min_row=2):
                for cell in row:
                    self.assertTrue(cell.alignment.wrap_text, "Cell in Candidates & Findings sheet must have wrap_text=True")
                row_h = ws_sanc.row_dimensions[row[0].row].height
                self.assertIsNotNone(row_h)
                self.assertGreaterEqual(row_h, 18)
        finally:
            if pdf_path.exists():
                pdf_path.unlink()
            if excel_path.exists():
                excel_path.unlink()


if __name__ == "__main__":
    unittest.main()
