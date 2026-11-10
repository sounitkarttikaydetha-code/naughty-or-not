import anyascii
from pathlib import Path
import re
from typing import Any, Dict, List

def sanitize_for_pdf(text: Any) -> str:
    """Sanitize any text for ReportLab Helvetica rendering, eliminating missing-glyph boxes."""
    if text is None:
        return "—"
    s = str(text)
    
    # Status markers to plain text
    emoji_map = {
        "🔴": "[RED] ",
        "🟠": "[AMBER] ",
        "ℹ️": "[INFO] ",
        "ℹ": "[INFO] ",
        "✅": "[CLEAR] ",
        "⚪": "[NOT CHECKED] ",
        "✈️": "[SAFETY] ",
        "✈": "[SAFETY] ",
        "📦": "[EXPORT CONTROL] ",
        "⚠️": "[WARNING] ",
        "⚠": "[WARNING] ",
        "🔍": "[SEARCH] ",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "•": "*",
    }
    for k, v in emoji_map.items():
        s = s.replace(k, v)
        
    # Transliterate characters outside Latin-1
    out = []
    for ch in s:
        try:
            ch.encode("latin-1")
            out.append(ch)
        except UnicodeEncodeError:
            out.append(anyascii.anyascii(ch))
    clean = "".join(out)
    
    # Escape HTML special chars except basic formatting tags
    # Let's ensure basic tags like <b>, </b>, <i>, </i>, <br/>, <font> are preserved
    parts = re.split(r'(</?[a-zA-Z0-9]+(?: [^>]+)?>)', clean)
    final_parts = []
    for p in parts:
        if p.startswith('<') and p.endswith('>'):
            final_parts.append(p)
        else:
            final_parts.append(p.replace("&", "&amp;"))
    return "".join(final_parts)

print("Sanitize test:")
print(sanitize_for_pdf("🔴 POTENTIAL MATCH: Сбербанк России / طيران ماهان / HAMAS — 'PJSC Aeroflot'"))
