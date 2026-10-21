"""
Script to compare live Watchman scores against ported Python scoring.
"""

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.watchman.client import WatchmanClient
import rapidfuzz.distance.JaroWinkler as rjw
import unicodedata

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower().replace(".", " ").replace(",", " ").replace("-", " ")
    clean = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            clean.append(" ")
        elif ch.isspace():
            clean.append(" ")
        else:
            clean.append(ch)
    s = "".join(clean)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = unicodedata.normalize("NFC", s)
    return " ".join(s.split())

def canonicalize_legal_forms(s: str) -> str:
    if not s:
        return s
    phrases = [
        ("limited liability company", "llc"),
        ("public limited company", "plc"),
        ("incorporated", "inc"),
        ("corporation", "corp"),
        ("company", "co"),
        ("limited", "ltd"),
    ]
    padded = " " + s + " "
    for f, t in phrases:
        padded = padded.replace(" " + f + " ", " " + t + " ")
    padded = padded.replace(" l l c ", " llc ").replace(" p l c ", " plc ")
    return padded.strip()

SOUNDEX_MAP = {
    "A": "A", "E": "A", "I": "A", "O": "A", "U": "A", "Y": "A",
    "B": "B", "F": "B", "P": "B", "V": "B",
    "C": "C", "G": "C", "J": "C", "K": "C", "Q": "C", "S": "C", "X": "C", "Z": "C",
    "D": "D", "T": "D",
    "L": "L",
    "M": "M", "N": "M",
    "R": "R",
    "H": "H", "W": "H",
}

def get_phonetic_class(s: str) -> str:
    if not s:
        return " "
    return SOUNDEX_MAP.get(s[0].upper(), s[0].upper())

def first_char_soundex_match(s1: str, s2: str) -> bool:
    if not s1 or not s2:
        return False
    return get_phonetic_class(s1) == get_phonetic_class(s2)

def generate_word_combinations(tokens):
    if len(tokens) <= 1:
        return [tokens]
    result = [tokens]
    forward = []
    skip = False
    for i in range(len(tokens)):
        if skip:
            skip = False
            continue
        if i < len(tokens) - 1 and len(tokens[i]) <= 3:
            forward.append(tokens[i] + tokens[i + 1])
            skip = True
        else:
            forward.append(tokens[i])
    if len(forward) < len(tokens):
        result.append(forward)
        backward = []
        for i in range(len(tokens)):
            if i > 0 and len(tokens[i]) <= 3 and len(backward) > 0:
                backward[-1] = backward[-1] + tokens[i]
            else:
                backward.append(tokens[i])
        if len(backward) < len(tokens) and backward != forward and backward != tokens:
            result.append(backward)
    return result

def best_pairs(search_tokens, index_tokens):
    scores = []
    for s_idx, s in enumerate(search_tokens):
        for i_idx, t in enumerate(index_tokens):
            if first_char_soundex_match(s, t):
                score = rjw.similarity(t, s, prefix_weight=0.1)
                ls, lt = len(s), len(t)
                ld = min(ls, lt) / max(ls, lt)
                if ld < 0.9:
                    score *= (1.0 - (1.0 - ld) * 0.3)
                scores.append((score, s_idx, i_idx))
    scores.sort(key=lambda x: x[0], reverse=True)
    m_s, m_i = set(), set()
    tot_weighted = 0.0
    matched_idx_len = 0
    for score, s_idx, i_idx in scores:
        if s_idx not in m_s and i_idx not in m_i:
            m_s.add(s_idx)
            m_i.add(i_idx)
            tot_weighted += score * (len(search_tokens[s_idx]) + len(index_tokens[i_idx]))
            matched_idx_len += len(index_tokens[i_idx])
    s_len = sum(len(x) for x in search_tokens)
    i_len = sum(len(x) for x in index_tokens)
    avg_score = tot_weighted / (s_len + matched_idx_len) if (s_len + matched_idx_len) else 0.0
    m_frac = matched_idx_len / i_len if i_len else 0.0
    return avg_score * (1.0 - (1.0 - m_frac) * 0.15)

def best_pair_combinations(search_tokens, index_tokens):
    s_combs = generate_word_combinations(search_tokens)
    i_combs = generate_word_combinations(index_tokens)
    max_score = 0.0
    for sc in s_combs:
        for ic in i_combs:
            sc_score = best_pairs(sc, ic)
            if sc_score > max_score:
                max_score = sc_score
    return max_score

def is_name_close_enough(q_tokens, i_tokens):
    qc = len(q_tokens)
    ic = len(i_tokens)
    if (qc / ic < 0.3) or (qc / ic > 3.0):
        return False
    match_count = 0
    for q in q_tokens:
        for it in i_tokens:
            if it in q or q in it:
                match_count += 1
                break
    return (match_count / qc) >= 0.4

def score_entity(query: str, entity: dict) -> float:
    q_norm = canonicalize_legal_forms(normalize_text(query))
    q_tokens = q_norm.split()

    names_to_check = []
    e_name = entity.get("name", "")
    i_norm = canonicalize_legal_forms(normalize_text(e_name))
    names_to_check.append((i_norm, False))

    biz = entity.get("business") or {}
    person = entity.get("person") or {}
    org = entity.get("organization") or {}
    alts = (biz.get("altNames") or []) + (person.get("altNames") or []) + (org.get("altNames") or [])
    for a in alts:
        names_to_check.append((canonicalize_legal_forms(normalize_text(a)), False))

    best_match = 0.0
    for n_str, is_hist in names_to_check:
        if not n_str:
            continue
        i_tokens = n_str.split()
        cand = best_pair_combinations(q_tokens, i_tokens)
        if is_hist:
            cand *= 0.95
        if cand > best_match:
            best_match = cand
            if best_match >= 0.99:
                break

    if len(q_tokens) >= 2:
        matching_terms = len(q_tokens) if best_match > 0.90 else 0
        if matching_terms < 2:
            best_match *= 0.8

    i_primary_tokens = i_norm.split()
    if not is_name_close_enough(q_tokens, i_primary_tokens):
        best_match *= 0.85

    return best_match * 0.81225

if __name__ == "__main__":
    client = WatchmanClient()
    for test_q in ["Sberbank", "VTB Bank", "Aeroflot"]:
        print(f"\n=== Query: {test_q} ===")
        res = client.search(test_q, min_match=0.70, limit=5)
        for e in res.get("results", {}).get("entities", []):
            wm_score = e.get("match", 0.0)
            py_score = score_entity(test_q, e)
            diff = abs(wm_score - py_score)
            sid = str(e.get("sourceID", ""))[:10]
            name = str(e.get("name", ""))[:35]
            print(f"{sid:10} | WM: {wm_score:.4f} | PY: {py_score:.4f} | Diff: {diff:.4f} | {name}")
