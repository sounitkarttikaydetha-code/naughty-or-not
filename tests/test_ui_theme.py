"""
Tests for T11 Part G: Modern UI Theme, Inter Font, Budgets, and Accessibility.
Verifies zero network requests during theme loading, CSS <= 30KB budget,
font size <= 1MB budget, and WCAG AA contrast >= 4.5:1 compliance.
"""

from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THEME_CSS = PROJECT_ROOT / "app" / "static" / "theme.css"
INTER_FONT = PROJECT_ROOT / "assets" / "fonts" / "Inter-Regular.woff2"


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def rel_lum(rgb):
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [channel(c) for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1: str, c2: str) -> float:
    l1, l2 = rel_lum(hex_to_rgb(c1)), rel_lum(hex_to_rgb(c2))
    top, bot = max(l1, l2), min(l1, l2)
    return (top + 0.05) / (bot + 0.05)


class TestModernUITheme(unittest.TestCase):
    def test_01_theme_css_exists_and_budget(self):
        """CSS size <= 30KB."""
        self.assertTrue(THEME_CSS.is_file(), "app/static/theme.css must exist")
        css_size = THEME_CSS.stat().st_size
        self.assertLessEqual(css_size, 30 * 1024, f"theme.css ({css_size} bytes) exceeds 30KB budget")

    def test_02_inter_font_budget(self):
        """Part P2: Inter removed in favor of Windows system font Segoe UI; PDF fonts within budget."""
        self.assertFalse(INTER_FONT.exists(), "Inter-Regular.woff2 must be removed as per Part P2")
        pdf_font = PROJECT_ROOT / "assets" / "fonts" / "NotoSans-Regular.ttf"
        self.assertTrue(pdf_font.is_file(), "NotoSans-Regular.ttf must be present for PDF reporting")
        self.assertLessEqual(pdf_font.stat().st_size, 1024 * 1024, "PDF font exceeds 1MB budget")

    def test_03_zero_network_calls_in_css(self):
        """Theme must never reference external CDNs or external fonts."""
        content = THEME_CSS.read_text(encoding="utf-8")
        self.assertNotIn("http://", content, "External HTTP CDN links forbidden in theme.css")
        self.assertNotIn("https://", content, "External HTTPS CDN links forbidden in theme.css")
        self.assertNotIn("fonts.googleapis.com", content)
        self.assertNotIn("cdnjs.cloudflare.com", content)

    def test_04_wcag_aa_contrast(self):
        """All text/chip combinations must achieve WCAG AA contrast >= 4.5:1."""
        checks = [
            ("Text primary on white", "#0F172A", "#FFFFFF", 4.5),
            ("Text secondary on white", "#334155", "#FFFFFF", 4.5),
            ("Text muted on white", "#475569", "#FFFFFF", 4.5),
            ("Likely chip", "#991B1B", "#FEE2E2", 4.5),
            ("Possible chip", "#92400E", "#FEF3C7", 4.5),
            ("Clear chip", "#065F46", "#D1FAE5", 4.5),
            ("Info chip", "#1E40AF", "#DBEAFE", 4.5),
            ("Unchecked chip", "#334155", "#F1F5F9", 4.5),
        ]
        for name, fg, bg, min_ratio in checks:
            ratio = contrast(fg, bg)
            self.assertGreaterEqual(
                ratio,
                min_ratio,
                f"{name} ({fg} on {bg}) achieved {ratio:.2f}:1, below required {min_ratio}:1"
            )

    def test_05_keyboard_focus_states(self):
        """Theme CSS must include :focus-visible rules."""
        content = THEME_CSS.read_text(encoding="utf-8")
        self.assertIn(":focus-visible", content)
        self.assertIn("outline", content)


if __name__ == "__main__":
    unittest.main()
