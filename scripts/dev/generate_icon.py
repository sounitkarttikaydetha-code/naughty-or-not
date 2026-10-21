"""
Generate professional application icon for Naughty or not.
Produces assets/icon.ico (multi-size: 16, 32, 48, 64, 128, 256) and assets/icon.png.
"""

from pathlib import Path
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

def create_icon_image(size: int = 256) -> Image.Image:
    # High-res RGBA image
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = size * 0.08
    w = size - 2 * pad
    h = size - 2 * pad

    # Draw rounded shield outline / base
    # Deep navy blue shield with gold trim
    shield_color = (24, 43, 73, 255)       # Navy
    border_color = (212, 175, 55, 255)    # Gold
    accent_color = (46, 204, 113, 255)    # Emerald check

    # Shield polygon coordinates
    x0, y0 = pad, pad
    x1, y1 = size - pad, pad
    cx = size / 2.0
    cy = size - pad

    # Outer shield shape
    points = [
        (cx, size - pad),
        (pad, size * 0.65),
        (pad, pad * 1.5),
        (cx, pad),
        (size - pad, pad * 1.5),
        (size - pad, size * 0.65),
    ]

    draw.polygon(points, fill=shield_color, outline=border_color, width=max(2, int(size * 0.04)))

    # Draw checkmark inside shield
    chk_w = max(3, int(size * 0.06))
    p1 = (cx - size * 0.18, pad + h * 0.45)
    p2 = (cx - size * 0.04, pad + h * 0.60)
    p3 = (cx + size * 0.22, pad + h * 0.30)

    draw.line([p1, p2, p3], fill=accent_color, width=chk_w, joint="curve")

    return img

def main():
    img_256 = create_icon_image(256)
    png_path = ASSETS_DIR / "icon.png"
    img_256.save(png_path, format="PNG")

    ico_path = ASSETS_DIR / "icon.ico"
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img_256.save(ico_path, format="ICO", sizes=sizes)
    print(f"Generated {png_path} and {ico_path} successfully!")

if __name__ == "__main__":
    main()
