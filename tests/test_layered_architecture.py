"""
Test suite validating strict Layered Architecture boundaries for Clearance Check Canary.
Uses Python AST inspection to enforce:
1. canary.domain never imports application, adapters, interfaces, or I/O packages.
2. canary.application never imports adapters or interfaces.
3. canary.adapters never imports interfaces.
"""
import ast
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANARY_DIR = PROJECT_ROOT / "canary"


def get_imports_from_file(file_path: Path) -> List[str]:
    """Parse a python file and extract all imported module names."""
    imports = []
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except Exception as e:
        raise RuntimeError(f"Error parsing {file_path}: {e}")
    return imports


def test_01_domain_layer_isolation():
    """Verify canary.domain is pure: no application, adapters, interfaces, or I/O imports."""
    domain_dir = CANARY_DIR / "domain"
    assert domain_dir.is_dir(), "canary/domain directory missing"

    forbidden_prefixes = [
        "canary.application",
        "canary.adapters",
        "canary.interfaces",
        "sqlite3",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "fastapi",
        "starlette",
        "flask",
    ]

    violations = []
    for py_file in domain_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        imports = get_imports_from_file(py_file)
        for imp in imports:
            for forb in forbidden_prefixes:
                if imp == forb or imp.startswith(f"{forb}."):
                    violations.append((str(py_file.relative_to(PROJECT_ROOT)), imp))

    assert not violations, f"Domain layer isolation violations found: {violations}"


def test_02_application_layer_isolation():
    """Verify canary.application imports only domain and standard ports; no adapters or interfaces."""
    app_dir = CANARY_DIR / "application"
    assert app_dir.is_dir(), "canary/application directory missing"

    forbidden_prefixes = [
        "canary.adapters",
        "canary.interfaces",
        "fastapi",
        "starlette",
        "sqlite3",
    ]

    violations = []
    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        imports = get_imports_from_file(py_file)
        for imp in imports:
            for forb in forbidden_prefixes:
                if imp == forb or imp.startswith(f"{forb}."):
                    violations.append((str(py_file.relative_to(PROJECT_ROOT)), imp))

    assert not violations, f"Application layer isolation violations found: {violations}"


def test_03_adapters_layer_isolation():
    """Verify canary.adapters never imports interfaces."""
    adapters_dir = CANARY_DIR / "adapters"
    assert adapters_dir.is_dir(), "canary/adapters directory missing"

    forbidden_prefixes = [
        "canary.interfaces",
    ]

    violations = []
    for py_file in adapters_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        imports = get_imports_from_file(py_file)
        for imp in imports:
            for forb in forbidden_prefixes:
                if imp == forb or imp.startswith(f"{forb}."):
                    violations.append((str(py_file.relative_to(PROJECT_ROOT)), imp))

    assert not violations, f"Adapters layer isolation violations found: {violations}"
