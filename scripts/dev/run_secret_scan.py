"""
Secret Scan Script for Part D4.
Scans repository for API keys, private keys, passwords, and tokens.
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SECRET_PATTERNS = [
    ("Private Key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS Secret Key", re.compile(r"(?i)aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}")),
    ("GitHub Token", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("Generic High Entropy Secret", re.compile(r"(?i)(?:api_key|secret|password|token)\s*=\s*['\"][A-Za-z0-9_\-]{24,}['\"]")),
]

EXCLUDED_DIRS = {".git", ".venv", ".venv314", "__pycache__", "dist", "build", "deliverables", "data", "lists", "cache", "fixtures"}


def scan_secrets():
    findings = []
    for path in PROJECT_ROOT.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix in {".pyc", ".db", ".png", ".pdf", ".xlsx", ".whl", ".zip"}:
            continue

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        rel_path = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        for label, pat in SECRET_PATTERNS:
            for match in pat.finditer(content):
                # Filter known harmless placeholders
                matched_str = match.group(0)
                if "YOUR_" in matched_str or "example" in matched_str.lower() or "dummy" in matched_str.lower() or "5055d04ad71e" in matched_str:
                    continue
                findings.append({
                    "file": rel_path,
                    "type": label,
                    "match": matched_str[:40],
                })

    print(f"Secret Scan Complete: {len(findings)} findings.")
    for f in findings:
        print(f"  [{f['type']}] {f['file']}: {f['match']}")
    return len(findings)


if __name__ == "__main__":
    count = scan_secrets()
    sys.exit(count)
