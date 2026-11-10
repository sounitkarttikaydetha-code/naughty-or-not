"""
Audit script for Part C1: Inventory of every emoji, pictograph, and symbol across
app.py, modules, docs, and templates.
Classifies each as functional, signature (Rule 9), or decorative.
"""
import re
import sys
import json
from pathlib import Path
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load status markers config
with open(PROJECT_ROOT / "config" / "status_markers.yaml", "r", encoding="utf-8") as f:
    markers_cfg = yaml.safe_load(f)

FUNCTIONAL_SYMBOLS = {m["symbol"] for m in markers_cfg["markers"].values()}
FUNCTIONAL_SYMBOLS.update({"\u2139", "\u2139\ufe0f", "✈", "✈️", "ℹ", "ℹ️"})
SIGNATURE_SYMBOLS = set(markers_cfg["signature"]["symbols"])

# Regex for emojis / pictographs
EMOJI_PATTERN = re.compile(
    r"["
    r"\U0001F300-\U0001F9FF"  # Misc Symbols and Pictographs, Supplemental Symbols
    r"\U0001FA00-\U0001FAFF"  # Symbols and Pictographs Extended-A
    r"\U00002139"             # Information source (ℹ)
    r"\U00002600-\U000026FF"  # Misc symbols (like ⚠️, ✈, ⚪, etc.)
    r"\U00002700-\U000027BF"  # Dingbats (like ✅, etc.)
    r"\U00002300-\U000023FF"  # Misc Technical (like ⏳, ⏰)
    r"\U00002B50-\U00002B55"  # Stars, circles (like ⭕)
    r"\U0000FE0F"             # Variation Selector-16
    r"]+",
    flags=re.UNICODE
)

EXCLUDED_DIRS = {".git", ".venv", ".venv314", "__pycache__", "node_modules", "dist", "build", "data", "lists", "fixtures"}
TARGET_EXTENSIONS = {".py", ".md", ".html", ".yaml", ".json", ".txt"}


def audit_symbols():
    inventory = []
    symbol_counts = {"functional": 0, "signature": 0, "decorative": 0}
    decorative_by_symbol = {}

    for path in PROJECT_ROOT.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in TARGET_EXTENSIONS:
            continue
        if "baseline" in path.name.lower() or "first_prompt" in path.name.lower():
            continue

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            continue

        rel_path = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        is_signature_file = rel_path in {
            "README.md", "app/about.py", "EASTER_EGG.txt", "app.py",
            "tests/fixtures/signature.txt", "scripts/dev/check_r1_signature.py"
        }

        for line_no, line in enumerate(lines, 1):
            matches = list(EMOJI_PATTERN.finditer(line))
            for match in matches:
                sym = match.group(0)
                # Clean variation selectors for classification if present
                base_sym = sym.replace("\ufe0f", "")
                
                # Determine classification
                is_func = any(f_sym in sym or f_sym.replace("\ufe0f", "") in base_sym for f_sym in FUNCTIONAL_SYMBOLS)
                is_sig = any(s_sym in sym for s_sym in SIGNATURE_SYMBOLS)

                if is_sig and is_signature_file and ("📸" in sym or "🕵️" in sym):
                    cls = "signature"
                    symbol_counts["signature"] += 1
                elif is_func:
                    cls = "functional"
                    symbol_counts["functional"] += 1
                else:
                    cls = "decorative"
                    symbol_counts["decorative"] += 1
                    decorative_by_symbol[sym] = decorative_by_symbol.get(sym, 0) + 1

                inventory.append({
                    "file": rel_path,
                    "line": line_no,
                    "symbol": sym,
                    "classification": cls,
                    "context": line.strip()[:100],
                })

    out_file = PROJECT_ROOT / "reviews" / "symbol_inventory.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "summary": symbol_counts,
            "decorative_summary": decorative_by_symbol,
            "total_symbols_found": len(inventory),
            "findings": inventory,
        }, f, indent=2, ensure_ascii=False)

    print("======================================================================")
    print("PART C1: SYMBOL AUDIT SUMMARY")
    print("======================================================================")
    print(f"Total symbol occurrences: {len(inventory)}")
    print(f"  • Functional (allowlist): {symbol_counts['functional']}")
    print(f"  • Rule 9 Signature:      {symbol_counts['signature']}")
    print(f"  • Decorative (TO REMOVE): {symbol_counts['decorative']}")
    print("----------------------------------------------------------------------")
    print("Top Decorative Symbols:")
    for sym, cnt in sorted(decorative_by_symbol.items(), key=lambda x: -x[1])[:15]:
        print(f"  {repr(sym)}: {cnt} occurrences")
    print(f"Audit results written to: {out_file}")
    return symbol_counts


if __name__ == "__main__":
    audit_symbols()
