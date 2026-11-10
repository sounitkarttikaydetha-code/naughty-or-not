"""
Generates clean vector SVG and multi-resolution ICO for Clearance Check icon.
Adheres to Part P6:
- Simple, original monochrome mark that reads at 16 px
- Shield outline, document silhouette, airplane detail, magnifying glass with checkmark
- No gradients, no cartoon style, no text inside the icon
- Uses accent colour from config/branding.yaml on transparent background
- Delivers assets/icon.svg, assets/icon_white.svg, assets/icon_256.png, assets/icon.ico, assets/favicon.ico
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
WHITE_RGB = (255, 255, 255)

def create_svg(color_hex):
    # ViewBox 0 0 256 256
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
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
  <!-- Check Mark inside Lens -->
  <path d="M 142 182 L 149 189 L 163 175" fill="none" stroke="{color_hex}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""
    return svg

def draw_icon_image(size, color_rgb, bg_rgba=(0, 0, 0, 0)):
    # Render crisp pixel-aligned geometry at target resolution
    img = Image.new("RGBA", (size, size), bg_rgba)
    draw = ImageDraw.Draw(img)
    scale = size / 256.0

    def s(coord):
        return coord * scale

    w_shield = max(1, int(round(14 * scale)))
    w_arc = max(1, int(round(7 * scale)))
    w_doc = max(1, int(round(9 * scale)))
    w_glass = max(1, int(round(9 * scale)))
    w_handle = max(1, int(round(11 * scale)))
    w_check = max(1, int(round(6 * scale)))
    w_bar = max(1, int(round(6 * scale)))

    if size >= 32:
        # Full detailed representation
        # 1. Outer shield
        shield_pts = [
            (s(128), s(16)), (s(176), s(20)), (s(220), s(52)), (s(222), s(100)),
            (s(205), s(156)), (s(170), s(205)), (s(128), s(238)),
            (s(86), s(205)), (s(51), s(156)), (s(34), s(100)), (s(36), s(52)), (s(80), s(20))
        ]
        draw.polygon([(x, y) for x, y in shield_pts], outline=color_rgb + (255,), width=w_shield)

        # 2. Airplane
        plane_pts = [
            (s(128), s(50)), (s(132), s(70)), (s(180), s(82)), (s(180), s(88)),
            (s(133), s(85)), (s(133), s(104)), (s(145), s(114)), (s(145), s(119)),
            (s(128), s(116)), (s(111), s(119)), (s(111), s(114)), (s(123), s(104)),
            (s(123), s(85)), (s(76), s(88)), (s(76), s(82)), (s(124), s(70))
        ]
        draw.polygon([(x, y) for x, y in plane_pts], fill=color_rgb + (255,))

        # 3. Document
        doc_pts = [
            (s(84), s(126)), (s(144), s(126)), (s(168), s(150)), (s(168), s(212)),
            (s(84), s(212))
        ]
        draw.polygon([(x, y) for x, y in doc_pts], outline=color_rgb + (255,), width=w_doc)
        draw.line([(s(144), s(126)), (s(144), s(150)), (s(168), s(150))], fill=color_rgb + (255,), width=w_doc)

        # Lines in doc
        draw.line([(s(96), s(152)), (s(130), s(152))], fill=color_rgb + (255,), width=w_bar)
        draw.line([(s(96), s(168)), (s(124), s(168))], fill=color_rgb + (255,), width=w_bar)
        draw.line([(s(96), s(184)), (s(116), s(184))], fill=color_rgb + (255,), width=w_bar)

        # 4. Magnifying glass
        cx, cy, r = s(152), s(182), s(24)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color_rgb + (255,), width=w_glass)
        draw.line([(s(169), s(199)), (s(190), s(220))], fill=color_rgb + (255,), width=w_handle)

        # Checkmark
        draw.line([(s(142), s(182)), (s(149), s(189))], fill=color_rgb + (255,), width=w_check)
        draw.line([(s(149), s(189)), (s(163), s(175))], fill=color_rgb + (255,), width=w_check)

    elif size >= 20:
        # Hand-tuned for 20-24px clarity
        draw.polygon([
            (s(128), 2), (s(220), 4), (s(222), s(120)), (s(128), size - 2),
            (s(34), s(120)), (s(36), 4)
        ], outline=color_rgb + (255,), width=2)
        cx, cy, r = s(130), s(135), s(45)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color_rgb + (255,), width=2)
        draw.line([(cx + r * 0.7, cy + r * 0.7), (size - 3, size - 3)], fill=color_rgb + (255,), width=2)
        draw.line([(cx - 3, cy), (cx, cy + 3)], fill=color_rgb + (255,), width=2)
        draw.line([(cx, cy + 3), (cx + 5, cy - 3)], fill=color_rgb + (255,), width=2)

    else:
        # 16px high-contrast pixel-crafted icon
        draw.polygon([(8, 1), (14, 2), (14, 8), (8, 14), (2, 8), (2, 2)], outline=color_rgb + (255,), width=1)
        draw.line([(5, 8), (7, 10)], fill=color_rgb + (255,), width=2)
        draw.line([(7, 10), (12, 5)], fill=color_rgb + (255,), width=2)

    return img

def main():
    # 1. Master SVG & White SVG
    svg_accent = create_svg(accent_color)
    with open(ASSETS_DIR / "icon.svg", "w", encoding="utf-8") as f:
        f.write(svg_accent)
    print("Generated assets/icon.svg")

    svg_white = create_svg("#FFFFFF")
    with open(ASSETS_DIR / "icon_white.svg", "w", encoding="utf-8") as f:
        f.write(svg_white)
    print("Generated assets/icon_white.svg")

    # 2. Render all required icon sizes
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = {}
    for sz in sizes:
        img = draw_icon_image(sz, ACCENT_RGB)
        images[sz] = img
        if sz in [16, 32, 64, 128, 256]:
            img.save(ASSETS_DIR / f"icon_{sz}.png")

    # Save 256 master png and icon.png
    images[256].save(ASSETS_DIR / "icon_256.png")
    images[256].save(ASSETS_DIR / "icon.png")
    print("Generated PNG sizes including assets/icon_256.png")

    # 3. Deliver assets/icon.ico with all sizes
    ico_path = ASSETS_DIR / "icon.ico"
    images[256].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes]
    )
    print(f"Generated multi-res icon: {ico_path} with sizes: {sizes}")

    # Favicon for web UI
    fav_path = ASSETS_DIR / "favicon.ico"
    images[32].save(fav_path, format="ICO", sizes=[(16, 16), (32, 32)])
    images[32].save(ASSETS_DIR / "favicon.png")
    print("Generated assets/favicon.ico and assets/favicon.png")

if __name__ == "__main__":
    main()
