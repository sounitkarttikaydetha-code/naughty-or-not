"""Generate easter egg for README.md and app/about.py."""
from pathlib import Path

words = ["WHY", "ARE", "YOU", "STILL", "SCROLLING"]
final_line = (
    "You actually scrolled all the way down here? Gotcha. Now smile for the camera. 📸. "
    "The developer got bored, you got curious and now we're even. Now go screen something. 🕵️ "
    "— Naughty or not, a brainchild of Sounit Karttikay (and the blood, sweat and tokens of Antigravity and Opus, "
    "no AIs were sanctioned in the making of this tool)"
)

# 1. README.md easter egg
md_parts = ["\n\n<!-- Easter Egg: Keep scrolling -->"]
for _ in range(25):
    md_parts.append("<br>")

for w_idx, word in enumerate(words):
    for l_idx, char in enumerate(word):
        md_parts.append(f'<p align="center"><b>{char}</b></p>')
        if l_idx < len(word) - 1:
            for _ in range(7):
                md_parts.append("<br>")
    if w_idx < len(words) - 1:
        for _ in range(14):
            md_parts.append("<br>")

for _ in range(20):
    md_parts.append("<br>")

md_parts.append(f"> {final_line}\n")
readme_append = "\n".join(md_parts)

readme_path = Path("README.md")
readme_text = readme_path.read_text(encoding="utf-8")
if "WHY ARE YOU STILL SCROLLING" not in readme_text:
    readme_path.write_text(readme_text.rstrip() + "\n" + readme_append, encoding="utf-8")
    print("Appended easter egg to README.md")

# 2. app/about.py
py_lines = [
    '"""About box metadata and credits for Naughty or not."""',
    'APP_NAME = "Naughty or not"',
    'APP_VERSION = "1.0.1"',
    'AUTHOR = "Sounit Karttikay"',
    'CREDITS = "Internal sanctions screening aid prepared under the Sanctions Compliance Policy."',
    "",
    "#",
]

for _ in range(30):
    py_lines.append("#")

for w_idx, word in enumerate(words):
    for l_idx, char in enumerate(word):
        py_lines.append(f"#  {char}")
        if l_idx < len(word) - 1:
            for _ in range(8):
                py_lines.append("#")
    if w_idx < len(words) - 1:
        for _ in range(16):
            py_lines.append("#")

for _ in range(25):
    py_lines.append("#")

py_lines.append(f"#  {final_line}")
py_lines.append("")

about_path = Path("app/about.py")
about_path.write_text("\n".join(py_lines), encoding="utf-8")
print("Wrote app/about.py")
