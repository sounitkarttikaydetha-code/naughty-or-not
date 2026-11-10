"""
Pure domain phonetic encoding using Double Metaphone.
Zero I/O.
"""
from typing import List, Tuple
import metaphone


def get_phonetic_code(word: str) -> str:
    """Return 'PRIMARY/SECONDARY' phonetic representation for a word."""
    if not word or len(word) < 3:
        return ""
    p_code, s_code = metaphone.doublemetaphone(word)
    p = p_code or ""
    s = s_code or ""
    if not p and not s:
        return ""
    if p == s:
        return f"{p}/"
    return f"{p}/{s}" if s else f"{p}/"


def get_tokens_phonetic_codes(tokens: List[str], min_len: int = 4) -> List[str]:
    """Generate list of phonetic codes for words meeting minimum length."""
    codes: List[str] = []
    for t in tokens:
        if len(t) >= min_len:
            c = get_phonetic_code(t)
            if c and c not in codes:
                codes.append(c)
    return codes


def phonetic_match_ratio(codes_a: List[str], codes_b: List[str]) -> float:
    """Return proportion of phonetic codes that match between two token sets."""
    if not codes_a or not codes_b:
        return 0.0

    def parse_codes(c_str: str) -> Tuple[str, str]:
        parts = c_str.split("/")
        return parts[0], parts[1] if len(parts) > 1 else ""

    parsed_b = [parse_codes(cb) for cb in codes_b]

    matched = 0
    for ca in codes_a:
        pa, sa = parse_codes(ca)
        hit = False
        for pb, sb in parsed_b:
            if pa and (pa == pb or (sb and pa == sb)):
                hit = True
                break
            if sa and (sa == pb or (sb and sa == sb)):
                hit = True
                break
        if hit:
            matched += 1

    return matched / max(len(codes_a), len(codes_b))
