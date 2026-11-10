import anyascii
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import pypdf

def sanitize_for_pdf(text: str) -> str:
    emoji_map = {
        '🔴': '[RED] ',
        '🟠': '[AMBER] ',
        'ℹ️': '[INFO] ',
        'ℹ': '[INFO] ',
        '✅': '[CLEAR] ',
        '⚪': '[NOT CHECKED] ',
        '✈️': '[SAFETY] ',
        '✈': '[SAFETY] ',
        '📦': '[EXPORT CONTROL] ',
        '⚠️': '[WARNING] ',
        '⚠': '[WARNING] ',
        '—': '-',
        '–': '-',
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
    }
    for k, v in emoji_map.items():
        text = text.replace(k, v)
    
    out = []
    for ch in text:
        try:
            ch.encode('latin-1')
            out.append(ch)
        except UnicodeEncodeError:
            out.append(anyascii.anyascii(ch))
    return ''.join(out)

raw_text = '🔴 LIKELY: Сбербанк России / طيران ماهان / Aeroflot — Russian Airlines'
clean_text = sanitize_for_pdf(raw_text)
print('Clean text:', clean_text)

doc = SimpleDocTemplate('test_clean.pdf')
styles = getSampleStyleSheet()
doc.build([Paragraph(clean_text, styles['Normal'])])

reader = pypdf.PdfReader('test_clean.pdf')
extracted = reader.pages[0].extract_text()
print('Extracted:', repr(extracted))
print('Missing glyph count:', extracted.count('\u25a0') + extracted.count('■'))
