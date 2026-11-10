"""
Audit script for Part R1: The author's signature check (Hard Rule 9).
Checks byte-for-byte match across all designated locations and fixture.
"""
import hashlib
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent

AGREED_LINE = (
    "You actually scrolled all the way down here? Gotcha. Now smile for the camera. 📸. "
    "The developer got bored, you got curious and now we're even. Now go screen something. 🕵️ "
    "— Naughty or not, a brainchild of Sounit Karttikay (and the blood, sweat and tokens of Antigravity and Opus, "
    "no AIs were sanctioned in the making of this tool)"
)

def main():
    agreed_bytes = AGREED_LINE.encode("utf-8")
    agreed_sha = hashlib.sha256(agreed_bytes).hexdigest()
    print("=" * 70)
    print("PART R1: AUTHOR SIGNATURE CHECK (HARD RULE 9)")
    print("=" * 70)
    print(f"Agreed Line: {AGREED_LINE}")
    print(f"Agreed UTF-8 Byte Length: {len(agreed_bytes)}")
    print(f"Agreed SHA-256: {agreed_sha}")
    print("-" * 70)

    locations = [
        ("README.md", ROOT / "README.md"),
        ("app/about.py", ROOT / "app" / "about.py"),
        ("EASTER_EGG.txt", ROOT / "EASTER_EGG.txt"),
        ("app.py (About dialog)", ROOT / "app.py"),
        ("tests/fixtures/signature.txt", ROOT / "tests" / "fixtures" / "signature.txt"),
    ]

    # Look for deploy / installer copies
    for extra in ["deploy/README.md", "installer/README.md", "dist/README.md"]:
        p = ROOT / extra
        if p.exists():
            locations.append((extra, p))

    all_matched = True
    for name, path in locations:
        if not path.exists():
            print(f"[-] {name}: File NOT FOUND at {path}")
            all_matched = False
            continue

        content = path.read_text(encoding="utf-8")
        if AGREED_LINE in content:
            print(f"[+] {name}: MATCH (exact agreed line present)")
        else:
            print(f"[-] {name}: MISMATCH! Signature line not found or differs.")
            all_matched = False

    # Check fixture exactness
    fix_path = ROOT / "tests" / "fixtures" / "signature.txt"
    if fix_path.exists():
        fix_bytes = fix_path.read_bytes()
        # Remove trailing CRLF/LF if any for exact hash check
        fix_clean = fix_path.read_text(encoding="utf-8").strip().encode("utf-8")
        fix_sha = hashlib.sha256(fix_clean).hexdigest()
        print(f"Fixture SHA-256 (stripped): {fix_sha}")
        if fix_sha == agreed_sha:
            print("[+] Fixture SHA-256 matches agreed SHA-256.")
        else:
            print("[-] Fixture SHA-256 differs!")
            all_matched = False

    print("=" * 70)
    if all_matched:
        print("[+] ALL SIGNATURE CHECKS PASSED.")
    else:
        print("[-] SIGNATURE CHECKS FAILED.")
    print("=" * 70)

if __name__ == "__main__":
    main()
