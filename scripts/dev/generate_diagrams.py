"""
Generate crisp, high-resolution architectural diagrams for Clearance Check Technical Dossier:
1. system_context.png
2. container.png
3. component.png
4. dataflow_name_check.png
5. dataflow_ownership_check.png
6. dataflow_list_refresh.png
Uses strict neutral corporate styling: Navy (#0F2A4A, #1E3A5F), Slate (#64748B), Light Slate (#F8FAFC), White (#FFFFFF).
Zero emojis.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIAGRAMS_DIR = PROJECT_ROOT / "docs" / "diagrams"
DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)

# Colors
NAVY = (15, 42, 74)
STEEL = (30, 58, 95)
SLATE = (100, 116, 139)
DARK_TEXT = (15, 23, 42)
LIGHT_BG = (248, 250, 252)
BOX_BG = (255, 255, 255)
BORDER_COL = (203, 213, 225)
ACCENT_GREEN = (22, 101, 52)
ACCENT_RED = (185, 28, 28)
ARROW_COL = (71, 85, 105)

# Try loading Windows system font Segoe UI or fallback
def get_fonts():
    try:
        title_font = ImageFont.truetype("segoeui.ttf", 26)
        hdr_font = ImageFont.truetype("segoeuib.ttf", 18)
        bold_font = ImageFont.truetype("segoeuib.ttf", 14)
        body_font = ImageFont.truetype("segoeui.ttf", 13)
        small_font = ImageFont.truetype("segoeui.ttf", 11)
    except Exception:
        title_font = ImageFont.load_default()
        hdr_font = ImageFont.load_default()
        bold_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    return title_font, hdr_font, bold_font, body_font, small_font

def draw_box(draw, x0, y0, w, h, title, subtitle="", items=None, border=STEEL, bg=BOX_BG, fill_title=STEEL):
    draw.rectangle([x0, y0, x0 + w, y0 + h], fill=bg, outline=border, width=2)
    # Header bar
    draw.rectangle([x0, y0, x0 + w, y0 + 32], fill=fill_title)
    _, hdr_font, bold_font, body_font, small_font = get_fonts()
    draw.text((x0 + 12, y0 + 6), title, fill=(255, 255, 255), font=bold_font)
    
    cur_y = y0 + 40
    if subtitle:
        draw.text((x0 + 12, cur_y), subtitle, fill=SLATE, font=small_font)
        cur_y += 18
    if items:
        for it in items:
            draw.text((x0 + 12, cur_y), f"• {it}", fill=DARK_TEXT, font=body_font)
            cur_y += 18

def draw_arrow(draw, p1, p2, text="", color=ARROW_COL):
    draw.line([p1, p2], fill=color, width=2)
    # Arrow head
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    dist = (dx**2 + dy**2)**0.5
    if dist > 0:
        ux, uy = dx / dist, dy / dist
        px, py = -uy, ux
        ah1 = (x2 - 10 * ux + 5 * px, y2 - 10 * uy + 5 * py)
        ah2 = (x2 - 10 * ux - 5 * px, y2 - 10 * uy - 5 * py)
        draw.polygon([p2, ah1, ah2], fill=color)
    if text:
        _, _, _, _, small_font = get_fonts()
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 14
        draw.text((mx + 6, my), text, fill=color, font=small_font)

# 1. System Context Diagram
def build_system_context():
    img = Image.new("RGB", (1200, 600), LIGHT_BG)
    draw = ImageDraw.Draw(img)
    t_font, h_font, b_font, bd_font, s_font = get_fonts()
    draw.text((40, 25), "System Context Diagram (C4 Level 1) — Clearance Check", fill=NAVY, font=t_font)
    draw.text((40, 60), "High-level environment boundaries, human actors, and external regulatory feeds", fill=SLATE, font=bd_font)

    # Actor: Compliance Officer
    draw_box(draw, 50, 180, 240, 220, "Compliance Officer", "Human Operator", [
        "Enters counterparty queries",
        "Performs manual review",
        "Executes UBO checks",
        "Exports PDF/Excel reports"
    ], border=STEEL, fill_title=STEEL)

    # Core System: Clearance Check
    draw_box(draw, 420, 140, 360, 300, "Clearance Check System", "Standalone Desktop / Server", [
        "Local Python 3.14 runtime",
        "Streamlit UI + WebView2 shell",
        "Watchman Jaro-Winkler scoring",
        "Phonetic & transliteration engine",
        "SQLite FTS5 raw text index",
        "Append-only local audit log"
    ], border=NAVY, fill_title=NAVY)

    # External Publishers
    draw_box(draw, 900, 100, 260, 240, "Regulatory Publishers", "External HTTPS Endpoints", [
        "US Treasury OFAC (SDN)",
        "US ITA (Consolidated List)",
        "UK FCDO (Sanctions List)",
        "EU Commission (DG FISMA)",
        "UN Security Council (UNSC)",
        "India MHA & DG MOVE / FAA"
    ], border=SLATE, fill_title=STEEL)

    # Optional OpenSanctions API
    draw_box(draw, 900, 380, 260, 150, "OpenSanctions API", "Optional External REST API", [
        "Commercial PEP/Sanctions",
        "Opt-in via user API key",
        "Isolated HTTPS requests"
    ], border=SLATE, fill_title=STEEL)

    # Connectors
    draw_arrow(draw, (290, 280), (420, 280), "Human UI Interaction")
    draw_arrow(draw, (780, 210), (900, 210), "24h List Sync (HTTPS)")
    draw_arrow(draw, (780, 420), (900, 420), "Opt-in Lookup (HTTPS)")

    img.save(DIAGRAMS_DIR / "system_context.png", dpi=(300, 300))
    print("Generated docs/diagrams/system_context.png")

# 2. Container Diagram
def build_container():
    img = Image.new("RGB", (1200, 650), LIGHT_BG)
    draw = ImageDraw.Draw(img)
    t_font, h_font, b_font, bd_font, s_font = get_fonts()
    draw.text((40, 25), "Container Diagram (C4 Level 2) — Clearance Check Process Model", fill=NAVY, font=t_font)
    draw.text((40, 60), "Local process architecture, inter-process boundaries, and persistent storage containers", fill=SLATE, font=bd_font)

    # Process boundary box
    draw.rectangle([40, 110, 1160, 600], fill=(255, 255, 255), outline=BORDER_COL, width=2)
    draw.text((60, 125), "Windows Desktop Host / Container Runtime Boundary", fill=SLATE, font=bd_font)

    # Shell
    draw_box(draw, 70, 180, 260, 160, "WebView2 Shell", "pywebview (Native GUI)", [
        "Edge Chromium engine",
        "Windows native window frame",
        "Binds localhost:8501"
    ], border=STEEL, fill_title=STEEL)

    # Streamlit Web App
    draw_box(draw, 400, 180, 320, 190, "Streamlit Web App", "Presentation Container", [
        "Python 3.14 runtime process",
        "Single-page UI components",
        "Display scaling & WCAG AA theme",
        "Session state management"
    ], border=NAVY, fill_title=NAVY)

    # Screening Engine
    draw_box(draw, 800, 180, 320, 210, "Screening Core Engine", "In-Process Python Module", [
        "Watchman Jaro-Winkler scoring",
        "0.81225 name-only ceiling",
        "Double Metaphone phonetics",
        "AnyAscii transliteration",
        "UBO 50% rule calculator"
    ], border=NAVY, fill_title=NAVY)

    # Local Storage
    draw_box(draw, 240, 420, 280, 150, "SQLite Databases", "Persistent Local Storage", [
        "raw_search.db (FTS5 Index)",
        "screening.db (WAL Audit Log)"
    ], border=SLATE, fill_title=STEEL)

    draw_box(draw, 640, 420, 320, 150, "Local File System", "%LOCALAPPDATA% / Volumes", [
        "lists/ (active XML/CSV lists)",
        "lists/archive/ (3-version backup)",
        "cache/ (SHA-256 verified pkl)",
        "reports/ (PDF & Excel outputs)"
    ], border=SLATE, fill_title=STEEL)

    # Connectors
    draw_arrow(draw, (330, 250), (400, 250), "Localhost HTTP")
    draw_arrow(draw, (720, 250), (800, 250), "Internal Call")
    draw_arrow(draw, (560, 370), (420, 420), "Read/Write SQL")
    draw_arrow(draw, (920, 390), (800, 420), "IO Operations")

    img.save(DIAGRAMS_DIR / "container.png", dpi=(300, 300))
    print("Generated docs/diagrams/container.png")

# 3. Component Diagram
def build_component():
    img = Image.new("RGB", (1200, 650), LIGHT_BG)
    draw = ImageDraw.Draw(img)
    t_font, h_font, b_font, bd_font, s_font = get_fonts()
    draw.text((40, 25), "Component Diagram (C4 Level 3) — Clearance Check Engine Modules", fill=NAVY, font=t_font)
    draw.text((40, 60), "Internal logical decomposition of Python modules and functional sub-systems", fill=SLATE, font=bd_font)

    # Presentation
    draw_box(draw, 50, 130, 240, 480, "Presentation Layer", "modules/common/ & app.py", [
        "app.py (Main Controller)",
        "branding.py (Branding rules)",
        "status_markers.yaml (Drawn)",
        "ownership/ui.py (UBO Tree)",
        "reporting/generator.py (PDF)",
        "reporting/logger.py (Audit)"
    ], border=STEEL, fill_title=STEEL)

    # Engine Core
    draw_box(draw, 340, 130, 260, 480, "Scoring & Screening", "modules/engine/ & screening/", [
        "scoring.py (Jaro-Winkler)",
        "name_prep.py (Clean & Norm)",
        "tiering.py (Tier evaluation)",
        "country.py (Country risk)",
        "identifiers.py (ID checks)",
        "reasons.py (Plain explanations)"
    ], border=NAVY, fill_title=NAVY)

    # Data Access & Ingestion
    draw_box(draw, 650, 130, 240, 480, "Ingestion & Data Access", "modules/common/ & raw_search/", [
        "source_manager.py (Sync)",
        "loader.py (List parsers)",
        "records_store.py (13 Sec)",
        "raw_search/engine.py (FTS5)",
        "raw_search/indexer.py (Index)"
    ], border=STEEL, fill_title=STEEL)

    # Ownership & External
    draw_box(draw, 940, 130, 220, 480, "UBO & Integrations", "modules/ownership/ & external", [
        "ownership/engine.py (50%)",
        "ownership/importer.py (File)",
        "aviation/client.py (Bans)",
        "fatf/client.py (Jurisdictions)",
        "india/parser.py (UAPA)",
        "opensanctions/client.py"
    ], border=SLATE, fill_title=STEEL)

    # Inter-component flows
    draw_arrow(draw, (290, 250), (340, 250), "Search Query")
    draw_arrow(draw, (600, 250), (650, 250), "Index Lookup")
    draw_arrow(draw, (340, 420), (290, 420), "Screening Verdict")
    draw_arrow(draw, (890, 250), (940, 250), "Entity Data")

    img.save(DIAGRAMS_DIR / "component.png", dpi=(300, 300))
    print("Generated docs/diagrams/component.png")

# 4. Data Flow: Name Check
def build_df_name_check():
    img = Image.new("RGB", (1200, 500), LIGHT_BG)
    draw = ImageDraw.Draw(img)
    t_font, h_font, b_font, bd_font, s_font = get_fonts()
    draw.text((40, 25), "Data Flow Diagram — Name Screening & Tiering Pipeline", fill=NAVY, font=t_font)
    draw.text((40, 60), "Deterministic step-by-step evaluation from raw counterparty string to compliance verdict", fill=SLATE, font=bd_font)

    steps = [
        ("1. User Input", ["Query text entry", "Type: Person/Org/Aero", "Optional DOB / Nat / ID"]),
        ("2. Name Prep", ["normalize_text()", "reorder_sdn_name()", "clean_company_name()", "get_transliteration()"]),
        ("3. Word Scoring", ["generate_word_combs()", "best_pairs_jaro_winkler()", "Length penalties", "0.81225 ceiling"]),
        ("4. Phonetic & ID", ["Double Metaphone match", "SOLAS IMO check-digit", "Corroboration upgrade", "Conflict downgrade"]),
        ("5. Tier Verdict", ["POTENTIAL_MATCH", "POSSIBLE_MATCH", "INFO / CLEAR", "SQLite audit log entry"])
    ]

    x = 40
    for idx, (title, items) in enumerate(steps):
        draw_box(draw, x, 140, 200, 260, title, "", items, border=NAVY if idx in (2, 4) else STEEL, fill_title=NAVY if idx in (2, 4) else STEEL)
        if idx < len(steps) - 1:
            draw_arrow(draw, (x + 200, 260), (x + 240, 260), "")
        x += 240

    img.save(DIAGRAMS_DIR / "dataflow_name_check.png", dpi=(300, 300))
    print("Generated docs/diagrams/dataflow_name_check.png")

# 5. Data Flow: Ownership Check
def build_df_ownership_check():
    img = Image.new("RGB", (1200, 500), LIGHT_BG)
    draw = ImageDraw.Draw(img)
    t_font, h_font, b_font, bd_font, s_font = get_fonts()
    draw.text((40, 25), "Data Flow Diagram — Beneficial Ownership (50% Rule) Calculation", fill=NAVY, font=t_font)
    draw.text((40, 60), "Aggregation across multi-tier corporate shareholding hierarchies under OFAC & EU/UK rules", fill=SLATE, font=bd_font)

    steps = [
        ("1. File Import", ["Upload Excel/Word tree", "Parse Shareholder table", "Parse Entity nodes", "Validate <=100%"]),
        ("2. Graph Build", ["Construct DAG hierarchy", "Detect circular cycles", "Calculate direct %", "Traverse intermediate"]),
        ("3. Sanctions Screen", ["Screen all entities", "Screen all shareholders", "Flag blocked owners", "Determine direct hold"]),
        ("4. Aggregation", ["OFAC >=50% rule sum", "EU/UK control condition", "Blocked intermediate check", "Chain-of-ownership"]),
        ("5. Audit & Report", ["Verdict (BLOCKED/CLEAR)", "Evidence breakdown table", "Interactive hierarchy tree", "Export PDF/Excel"])
    ]

    x = 40
    for idx, (title, items) in enumerate(steps):
        draw_box(draw, x, 140, 200, 260, title, "", items, border=NAVY if idx in (3, 4) else STEEL, fill_title=NAVY if idx in (3, 4) else STEEL)
        if idx < len(steps) - 1:
            draw_arrow(draw, (x + 200, 260), (x + 240, 260), "")
        x += 240

    img.save(DIAGRAMS_DIR / "dataflow_ownership_check.png", dpi=(300, 300))
    print("Generated docs/diagrams/dataflow_ownership_check.png")

# 6. Data Flow: List Refresh
def build_df_list_refresh():
    img = Image.new("RGB", (1200, 500), LIGHT_BG)
    draw = ImageDraw.Draw(img)
    t_font, h_font, b_font, bd_font, s_font = get_fonts()
    draw.text((40, 25), "Data Flow Diagram — Regulatory List Freshness & Atomic Swap", fill=NAVY, font=t_font)
    draw.text((40, 60), "Automated 24h update cycle, schema validation, 3-version archive, and atomic index swap", fill=SLATE, font=bd_font)

    steps = [
        ("1. Trigger / Check", ["24-hour periodic worker", "Manual 'Update lists' click", "Check HTTP headers / 304", "Verify allowed domain"]),
        ("2. Secure Fetch", ["HTTPS TLS 1.2/1.3 only", "Strict URL allowlist", "Zero user data sent", "Download to .tmp file"]),
        ("3. Validation", ["Format & schema check", "Record count boundary", "Required columns exist", "Check closure text"]),
        ("4. Atomic Swap", ["Archive previous copy", "Keep previous 3 versions", "Atomic rename tmp->active", "Update sources_state.json"]),
        ("5. Re-Index", ["Rebuild SQLite FTS5", "Invalidate disk cache", "Recompute composite SHA", "Write .sha256 hash file"])
    ]

    x = 40
    for idx, (title, items) in enumerate(steps):
        draw_box(draw, x, 140, 200, 260, title, "", items, border=NAVY if idx in (3, 4) else STEEL, fill_title=NAVY if idx in (3, 4) else STEEL)
        if idx < len(steps) - 1:
            draw_arrow(draw, (x + 200, 260), (x + 240, 260), "")
        x += 240

    img.save(DIAGRAMS_DIR / "dataflow_list_refresh.png", dpi=(300, 300))
    print("Generated docs/diagrams/dataflow_list_refresh.png")

if __name__ == "__main__":
    build_system_context()
    build_container()
    build_component()
    build_df_name_check()
    build_df_ownership_check()
    build_df_list_refresh()
