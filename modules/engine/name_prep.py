"""
Name Preparation Pipeline
Ported from moov-io/watchman (v1.2.2):
- internal/prepare/pipeline_normalize.go
- internal/prepare/pipeline_company_name_cleanup.go
- internal/prepare/pipeline_legal_forms.go
- internal/prepare/pipeline_reorder.go
- internal/prepare/pipeline_ex_names.go
- pkg/search/models.go
"""

import json
import os
from pathlib import Path
import re
import unicodedata
from typing import List, Optional, Tuple

# Reorder SDN names pattern:
# looks for: a comma, optional whitespace, then letters/diacritics/apostrophes/hyphens/spaces to end of string
SURNAME_PRECEDES_RE = re.compile(r",(?:\s+)?([\w\s'\-.\u00C0-\u024F\u1E00-\u1EFF]+)$")

# English legal forms mapping
ENGLISH_LEGAL_FORM_PHRASES = [
    ("limited liability company", "llc"),
    ("public limited company", "plc"),
    ("incorporated", "inc"),
    ("corporation", "corp"),
    ("company", "co"),
    ("limited", "ltd"),
]

SPACED_LEGAL_FORM_TOKENS = ["llc", "plc"]

# Former name markers
FORMER_MARKERS = [
    "formerly known as",
    "f.k.a.",
    "f/k/a",
    "f.k.a",
    "formerly",
]

# Number regex from Watchman internal/prepare/pipeline_stopwords.go:
# numberRegex = regexp.MustCompile(`([\d\.\,\-]{1,}[\d]{1,})`)
NUMBER_REGEX = re.compile(r"[\d.,-]{1,}\d")

# English stopwords from bbalet/stopwords
ENGLISH_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "ao", "are", "aren't", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further",
    "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very",
    "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when",
    "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't",
    "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}


def remove_stopwords(text: str) -> List[str]:
    """
    Port of Watchman prepare.RemoveStopwords.
    Short acronyms/codes (<= 3 chars, e.g. 's7', 'vtb', 'ast') have unknown language
    in whatlanggo and are returned as single unsegmented tokens.
    Leaves numbers matching NUMBER_REGEX untouched; segments other words into
    letter sequences and drops English stopwords.
    """
    if not text:
        return []
    clean = text.strip().lower()
    if len(clean) <= 3 and not clean.isspace():
        return [clean]

    tokens = []
    for w in clean.split():
        m = NUMBER_REGEX.search(w)
        if m and m.group(0) == w:
            tokens.append(w)
            continue
        segments = re.findall(r"[^\W_]+", w)
        for seg in segments:
            # Keep single-character initials (like A., M., etc.) matching Watchman's unknown-lang behavior
            if len(seg) == 1:
                tokens.append(seg)
                continue
            if seg in ENGLISH_STOPWORDS:
                continue
            if seg:
                tokens.append(seg)
    return tokens


def reorder_sdn_name(name: str, sdn_type: str) -> str:
    """
    Port of prepare.ReorderSDNName.
    Reorders 'Surname, GivenNames' to 'GivenNames Surname' for individuals.
    """
    if not name or sdn_type.lower() != "individual":
        return name

    m = SURNAME_PRECEDES_RE.search(name)
    if not m:
        return name

    match_full = m.group(0)
    given_names = m.group(1).strip()
    surname = name[: -len(match_full)].strip()
    return f"{given_names} {surname}".strip()


def split_ex_names(s: str) -> Tuple[str, List[str]]:
    """
    Port of prepare.SplitExNames.
    Extracts former / historical names in parentheses (e.g. '(ex-Cape Diamond)', '(f.k.a. ...)')
    and returns (cleaned_current_name, list_of_former_names).
    """
    if not s or not s.strip():
        return "", []

    former: List[str] = []
    text = s.strip()

    # Match parenthesized parts
    def _check_inner(inner: str) -> List[str]:
        inner_clean = inner.strip()
        lower = inner_clean.lower()
        if lower.startswith("ex-") or lower.startswith("ex "):
            rest = inner_clean[3:].strip()
            return [x.strip() for x in rest.split(",") if x.strip()]
        for marker in FORMER_MARKERS:
            if lower.startswith(marker):
                rest = inner_clean[len(marker):].lstrip(" :-,").strip()
                return [x.strip() for x in rest.split(",") if x.strip()]
        return []

    cleaned_parts = []
    i = 0
    while i < len(text):
        start = text.find("(", i)
        if start < 0:
            cleaned_parts.append(text[i:])
            break
        cleaned_parts.append(text[i:start])
        end = text.find(")", start)
        if end < 0:
            cleaned_parts.append(text[start:])
            break
        inner = text[start + 1: end]
        found = _check_inner(inner)
        if found:
            former.extend(found)
        else:
            cleaned_parts.append(text[start: end + 1])
        i = end + 1

    cleaned = " ".join("".join(cleaned_parts).split())
    return cleaned, former


def normalize_text(s: str) -> str:
    """
    Port of prepare.LowerAndRemovePunctuation.
    - Lowers case
    - Replaces '.', ',', '-' with spaces
    - Replaces unicode punctuation and symbols with spaces
    - Decomposes accents (NFD), removes nonspacing marks (Mn), recomposes NFC
    - Collapses whitespaces
    """
    if not s:
        return ""

    lowered = s.lower().replace(".", " ").replace(",", " ").replace("-", " ")
    cleaned_chars = []
    for ch in lowered:
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            cleaned_chars.append(" ")
        elif ch.isspace():
            cleaned_chars.append(" ")
        elif ch.isalnum():
            cleaned_chars.append(ch)
    joined = "".join(cleaned_chars)

    # Unicode NFD -> strip Mn -> NFC
    decomposed = unicodedata.normalize("NFD", joined)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    recomposed = unicodedata.normalize("NFC", stripped)
    return " ".join(recomposed.split())


def canonicalize_legal_forms(s: str) -> str:
    """
    Port of prepare.CanonicalizeEnglishLegalForms.
    Rewrites English legal forms to short canonical tokens.
    """
    if not s:
        return ""
    padded = f" {s} "
    for f, t in ENGLISH_LEGAL_FORM_PHRASES:
        padded = padded.replace(f" {f} ", f" {t} ")
    for short in SPACED_LEGAL_FORM_TOKENS:
        spaced = " " + " ".join(list(short)) + " "
        padded = padded.replace(spaced, f" {short} ")
    return " ".join(padded.split())


def prepare_name(name: str, entity_type: str = "") -> Tuple[str, List[str]]:
    """
    Full Watchman name preparation pipeline (models.go prepareEntityName).
    Returns (normalized_name, former_names).
    """
    cleaned, former = split_ex_names(name)
    norm = normalize_text(cleaned)
    if entity_type.lower() in ["business", "organisation", "organization", ""]:
        norm = canonicalize_legal_forms(norm)
    norm_former = [normalize_text(f) for f in former if f.strip()]
    return norm, norm_former


def is_non_latin(text: str) -> bool:
    """Return True if text contains characters from non-Latin scripts (Cyrillic, Arabic, Han, etc.)."""
    for ch in text:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            if not ("LATIN" in name):
                return True
    return False


def get_transliteration(text: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if text contains non-Latin characters and return transliteration using anyascii if available.
    Returns (is_non_latin, warning_message, transliterated_text).
    """
    if not is_non_latin(text):
        return False, None, None

    warning = "This name contains non-Latin characters. Automatic matching is limited — also use Text search and Manual check."
    transliterated = None
    try:
        import anyascii
        tl = anyascii.anyascii(text).strip()
        if tl and tl.lower() != text.lower():
            transliterated = tl
    except ImportError:
        pass

    return True, warning, transliterated
