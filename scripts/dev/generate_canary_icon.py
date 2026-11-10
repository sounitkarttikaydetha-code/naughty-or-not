"""
Generates clean vector SVG and multi-resolution ICO for Clearance Check Canary icon.
Adheres to Part P and Canary specification:
- Based on the v1.2.1 icon with a distinct small 'C' vector badge in the corner.
- Redrawn as vector, sharp at all resolutions (16px to 256px).
- Generates assets/icon_canary.svg, assets/icon_canary_white.svg, assets/icon_canary.ico,
  and PNG sizes (16, 32, 64, 128, 256).
"""
from pathlib import Path
import yaml
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Load branding accent color
branding_file = PROJECT_ROOT / "config" / "branding.yaml"
accent_color = "#1E3A5F"
if branding_file.exists():
    with open(branding_file, "r", encoding="utf-8") as f:
        bdata = yaml.safe_load(f) or {}
        accent_color = bdata.get("accent_color", "#1E3A5F")

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

ACCENT_RGB = hex_to_rgb(accent_color)
AMBER_RGB = (191, 54, 12)  # #BF360C - corporate amber for Canary marker
WHITE_RGB = (255, 255, 255)

def create_canary_svg(color_hex: str, badge_bg: str = "#BF360C", badge_text: str = "#FFFFFF") -> str:
    """Master SVG with 'C' badge in top-right corner."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <!-- Outer Shield Contour -->
  <path d="M 128 16 C 176 16, 224 32, 224 56 C 224 148, 176 216, 128 240 C 80 216, 32 148, 32 56 C 32 32, 80 16, 128 16 Z" 
        fill="none" stroke="{color_hex}" stroke-width="14" stroke-linejoin="round" stroke-linecap="round"/>
  
  <!-- Aviation Horizon Arc -->
  <path d="M 54 116 C 88 92, 168 92, 202 116" 
        fill="none" stroke="{color_hex}" stroke-width="7" stroke-linecap="round"/>

  <!-- Airplane Silhouette -->
  <path d="M 128 50 L 132 70 L 180 82 L 180 88 L 133 85 L 133 104 L 145 114 L 145 119 L 128 116 L 111 119 L 111 114 L 123 104 L 123 85 L 76 88 L 76 82 L 124 70 Z" 
        fill="{color_hex}"/>

  <!-- Document Sheet -->
  <path d="M 88 126 L 144 126 L 168 150 L 168 206 C 168 210, 164 214, 160 214 L 88 214 C 84 214, 80 210, 80 206 L 80 134 C 80 130, 84 126, 88 126 Z" 
        fill="none" stroke="{color_hex}" stroke-width="9" stroke-linejoin="round"/>
  <!-- Document Fold Corner -->
  <path d="M 144 126 L 144 150 L 168 150" fill="none" stroke="{color_hex}" stroke-width="9" stroke-linejoin="round"/>
  <!-- Document Text Bars -->
  <line x1="96" y1="152" x2="132" y2="152" stroke="{color_hex}" stroke-width="6" stroke-linecap="round"/>
  <line x1="96" y1="168" x2="128" y2="168" stroke="{color_hex}" stroke-width="6" stroke-linecap="round"/>
  <line x1="96" y1="184" x2="118" y2="184" stroke="{color_hex}" stroke-width="6" stroke-linecap="round"/>

  <!-- Magnifying Glass with Check Mark -->
  <circle cx="152" cy="182" r="24" fill="none" stroke="{color_hex}" stroke-width="9"/>
  <line x1="169" y1="199" x2="188" y2="218" stroke="{color_hex}" stroke-width="11" stroke-linecap="round"/>
  <polyline points="142,182 149,189 163,175" fill="none" stroke="{color_hex}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>

  <!-- Vector 'C' Canary Badge in Top-Right Corner -->
  <g id="canary-badge">
    <circle cx="204" cy="46" r="32" fill="{badge_bg}" stroke="#FFFFFF" stroke-width="5"/>
    <path d="M 216 35 C 210 27, 192 27, 188 46 C 185 62, 204 67, 216 57" 
          fill="none" stroke="{badge_text}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
</svg>"""

def draw_canary_icon_image(size: int, color_rgb: tuple) -> Image.Image:
    """Draw pixel-crafted Canary icon at any resolution with 'C' badge."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def s(v):
        return int(round(v * size / 256.0))

    if size >= 32:
        w_shield = max(1, s(14))
        w_doc = max(1, s(9))
        w_bar = max(1, s(6))
        w_glass = max(1, s(9))
        w_handle = max(2, s(11))
        w_check = max(1, s(7))

        shield_pts = [
            (s(128), s(16)), (s(224), s(56)), (s(224), s(148)),
            (s(128), s(240)), (s(32), s(148)), (s(32), s(56))
        ]
        draw.polygon([(x, y) for x, y in shield_pts], outline=color_rgb + (255,), width=w_shield)

        plane_pts = [
            (s(128), s(50)), (s(132), s(70)), (s(180), s(82)), (s(180), s(88)),
            (s(133), s(85)), (s(133), s(104)), (s(145), s(114)), (s(145), s(119)),
            (s(128), s(116)), (s(111), s(119)), (s(111), s(114)), (s(123), s(104)),
            (s(123), s(85)), (s(76), s(88)), (s(76), s(82)), (s(124), s(70))
        ]
        draw.polygon([(x, y) for x, y in plane_pts], fill=color_rgb + (255,))

        doc_pts = [
            (s(84), s(126)), (s(144), s(126)), (s(168), s(150)), (s(168), s(212)),
            (s(84), s(212))
        ]
        draw.polygon([(x, y) for x, y in doc_pts], outline=color_rgb + (255,), width=w_doc)
        draw.line([(s(144), s(126)), (s(144), s(150)), (s(168), s(150))], fill=color_rgb + (255,), width=w_doc)

        draw.line([(s(96), s(152)), (s(130), s(152))], fill=color_rgb + (255,), width=w_bar)
        draw.line([(s(96), s(168)), (s(124), s(168))], fill=color_rgb + (255,), width=w_bar)
        draw.line([(s(96), s(184)), (s(116), s(184))], fill=color_rgb + (255,), width=w_bar)

        cx, cy, r = s(152), s(182), s(24)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color_rgb + (255,), width=w_glass)
        draw.line([(s(169), s(199)), (s(190), s(220))], fill=color_rgb + (255,), width=w_handle)

        draw.line([(s(142), s(182)), (s(149), s(189))], fill=color_rgb + (255,), width=w_check)
        draw.line([(s(149), s(189)), (s(163), s(175))], fill=color_rgb + (255,), width=w_check)

        # 'C' Badge
        bcx, bcy, br = s(204), s(46), max(4, s(32))
        bw = max(1, s(5))
        draw.ellipse([bcx - br, bcy - br, bcx + br, bcy + br], fill=AMBER_RGB + (255,), outline=WHITE_RGB + (255,), width=bw)
        c_r = max(2, int(br * 0.58))
        draw.arc([bcx - c_r, bcy - c_r, bcx + c_r, bcy + c_r], start=45, end=315, fill=WHITE_RGB + (255,), width=max(1, s(8)))

    elif size >= 20:
        draw.polygon([
            (s(128), 2), (s(220), 4), (s(222), s(120)), (s(128), size - 2),
            (s(34), s(120)), (s(36), 4)
        ], outline=color_rgb + (255,), width=2)
        cx, cy, r = s(130), s(135), s(45)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color_rgb + (255,), width=2)
        draw.line([(cx + r * 0.7, cy + r * 0.7), (size - 3, size - 3)], fill=color_rgb + (255,), width=2)
        draw.line([(cx - 3, cy), (cx, cy + 3)], fill=color_rgb + (255,), width=2)
        draw.line([(cx, cy + 3), (cx + 5, cy - 3)], fill=color_rgb + (255,), width=2)

        draw.ellipse([size - 9, 1, size - 1, 9], fill=AMBER_RGB + (255,), outline=WHITE_RGB + (255,), width=1)
        draw.arc([size - 8, 2, size - 2, 8], start=45, end=315, fill=WHITE_RGB + (255,), width=2)

    else:
        draw.polygon([(8, 1), (14, 2), (14, 8), (8, 14), (2, 8), (2, 2)], outline=color_rgb + (255,), width=1)
        draw.line([(5, 8), (7, 10)], fill=color_rgb + (255,), width=2)
        draw.line([(7, 10), (12, 5)], fill=color_rgb + (255,), width=2)
        draw.ellipse([10, 0, 15, 5], fill=AMBER_RGB + (255,))
        draw.point([(12, 1), (11, 2), (11, 3), (12, 4)], fill=WHITE_RGB + (255,))

    return img

def main():
    svg_accent = create_canary_svg(accent_color)
    with open(ASSETS_DIR / "icon_canary.svg", "w", encoding="utf-8") as f:
        f.write(svg_accent)
    print("Generated assets/icon_canary.svg")

    svg_white = create_canary_svg("#FFFFFF", badge_bg="#BF360C", badge_text="#FFFFFF")
    with open(ASSETS_DIR / "icon_canary_white.svg", "w", encoding="utf-8") as f:
        f.write(svg_white)
    print("Generated assets/icon_canary_white.svg")

    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = {}
    for sz in sizes:
        img = draw_canary_icon_image(sz, ACCENT_RGB)
        images[sz] = img
        if sz in [16, 32, 64, 128, 256]:
            img.save(ASSETS_DIR / f"icon_canary_{sz}.png")

    images[256].save(ASSETS_DIR / "icon_canary_256.png")
    images[256].save(ASSETS_DIR / "icon_canary.png")
    print("Generated PNG sizes including assets/icon_canary_256.png")

    ico_path = ASSETS_DIR / "icon_canary.ico"
    images[256].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes]
    )
    print(f"Generated multi-res icon: {ico_path} with sizes: {sizes}")

    fav_path = ASSETS_DIR / "favicon_canary.ico"
    images[32].save(fav_path, format="ICO", sizes=[(16, 16), (32, 32)])
    images[32].save(ASSETS_DIR / "favicon_canary.png")
    print("Generated assets/favicon_canary.ico and assets/favicon_canary.png")

if __name__ == "__main__":
    main()
