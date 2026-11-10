"""
Pure domain normalisation and tokenisation.
Zero I/O. Operates on strings and collections in memory.
"""
import re
import unicodedata
from typing import List, Set, Dict, Optional

# Default domain wordlists
DEFAULT_WEAK_WORDS = [
    "the", "and", "of", "in", "for", "to", "at", "by", "from",
    "co", "company", "group", "holdings", "enterprise", "enterprises",
    "services", "trading", "international", "corp", "corporation",
    "ltd", "limited", "inc", "incorporated", "llc", "gmbh", "sa",
    "bv", "nv", "srl", "sl", "spa", "ag", "as", "oy", "ab",
    "bank", "air", "airline", "airlines", "transport", "logistics"
]

DEFAULT_COMPANY_TYPE_WORDS = [
    "ltd", "limited", "inc", "incorporated", "corp", "corporation",
    "llc", "llp", "gmbh", "sa", "s a", "s.a.", "s.a", "bv", "nv",
    "srl", "sl", "s.l.", "spa", "s.p.a.", "ag", "as", "oy", "ab",
    "pjsc", "jsc", "ojsc", "cjsc", "pao", "oao", "zao",
    "public joint stock company", "joint stock company",
    "closed joint stock company", "open joint stock company",
    "pvt ltd", "private limited", "pty ltd", "proprietary limited",
    "plc", "public limited company", "holding", "holdings",
    "group", "co", "company"
]

DEFAULT_COUNTRY_WORDS = [
    "russia", "russian", "iran", "iranian", "syria", "syrian",
    "korea", "north korea", "dprk", "cuba", "cuban", "venezuela",
    "venezuelan", "myanmar", "burma", "burmese", "belarus", "belarusian",
    "india", "indian", "china", "chinese", "uk", "united kingdom",
    "usa", "united states", "america", "american", "uae", "emirates",
    "dubai", "abu dhabi", "singapore", "hong kong", "switzerland",
    "swiss", "cyprus", "cypriot", "malta", "maltese", "panama",
    "panamanian", "liberia", "liberian", "marshall islands"
]

DEFAULT_KNOWN_CITIES = [
    "moscow", "saint petersburg", "tehran", "damascus", "pyongyang",
    "havana", "caracas", "minsk", "dubai", "london", "new york",
    "singapore", "hong kong", "geneva", "zurich", "mumbai", "delhi"
]

DEFAULT_NAME_VARIANTS = {
    "mohammed": "mohammad",
    "muhammad": "mohammad",
    "mohamed": "mohammad",
    "vladimir": "vladimir",
    "wladimir": "vladimir",
    "yevgeny": "yevgeny",
    "evgeniy": "yevgeny",
    "qaddafi": "qadhafi",
    "kadhafi": "qadhafi",
    "gadhafi": "qadhafi",
    "hussein": "hussein",
    "husayn": "hussein",
    "chaudhary": "chaudhary",
    "choudhary": "chaudhary",
    "sheikh": "sheikh",
    "shaikh": "sheikh",
}


def fold_accents(text: str) -> str:
    """Fold accents and diacritics to pure ASCII equivalent."""
    if not text:
        return ""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")


def normalize_tokens(
    text: str,
    company_words: Optional[List[str]] = None,
    name_variants: Optional[Dict[str, str]] = None,
) -> List[str]:
    """
    Normalise a name or alias string into clean core tokens:
    - Lowercase
    - Fold accents / diacritics
    - Strip punctuation
    - Remove company type words
    - Map transliteration/spelling variants
    """
    if not text:
        return []

    c_words = company_words or DEFAULT_COMPANY_TYPE_WORDS
    variants = name_variants or DEFAULT_NAME_VARIANTS

    s = text.lower()
    s = fold_accents(s)
    s = s.replace("-", " ")

    # Remove multi-word phrases first
    multi_phrases = [w.lower().replace("-", " ") for w in c_words if " " in w or "-" in w]
    for phrase in sorted(multi_phrases, key=len, reverse=True):
        pattern = r"\b" + re.escape(" ".join(phrase.split())) + r"\b"
        s = re.sub(pattern, " ", s)

    # Remove punctuation
    s = re.sub(r"[^\w\s]", " ", s)

    tokens = s.split()
    single_set = {w.lower() for w in c_words if " " not in w and "-" not in w}
    single_set.update({"joint", "stock", "commercial", "enterprise", "industrial"})

    core = [
        variants.get(w, w)
        for w in tokens
        if w and w not in single_set
    ]
    return core


def is_ignorable_bracket_content(
    content: str,
    country_words: Optional[List[str]] = None,
    company_words: Optional[List[str]] = None,
    weak_words: Optional[List[str]] = None,
    cities: Optional[List[str]] = None,
) -> bool:
    """True if bracket text contains only country, city, legal form, or weak words."""
    tokens = normalize_tokens(content, company_words=company_words)
    if not tokens:
        return True

    cw = country_words or DEFAULT_COUNTRY_WORDS
    comp = company_words or DEFAULT_COMPANY_TYPE_WORDS
    ww = weak_words or DEFAULT_WEAK_WORDS
    ct = cities or DEFAULT_KNOWN_CITIES

    ignorable_set = {w.lower() for w in (cw + comp + ww + ct)}
    return all(t in ignorable_set for t in tokens)


def split_alias_text(text: str) -> List[str]:
    """
    Split name on brackets and d/b/a, a.k.a., f.k.a., formerly, semicolons.
    Discards brackets that are purely ignorable countries, forms, or cities.
    """
    if not text:
        return []

    raw_brackets = re.findall(r"[\(\[\{]([^\)\]\}]+)[\)\]\}]", text)
    outside = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", text)
    valid_brackets = [b.strip() for b in raw_brackets if not is_ignorable_bracket_content(b)]

    delims = [r";", r"/", r"\ba\.?k\.?a\.?\b", r"\bf\.?k\.?a\.?\b", r"\bd\.?b\.?a\.?\b", r"\bformerly\b"]
    pattern = "|".join(delims)
    outside_parts = re.split(pattern, outside, flags=re.IGNORECASE)

    results = []
    seen = set()
    for part in outside_parts + valid_brackets:
        cleaned = re.sub(r"\s+", " ", part).strip()
        if cleaned and len(cleaned) >= 2 and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            results.append(cleaned)

    return results
