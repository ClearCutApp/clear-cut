"""Layer-boundary guard (AGENT.md Section 2).

`domain/` may import only the standard library or `clearcut.domain` itself.
`application/` may import `clearcut.domain`, but never a web framework, a
third-party client, or `clearcut.adapters`.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_DIR = REPO_ROOT / "src" / "clearcut" / "domain"
APPLICATION_DIR = REPO_ROOT / "src" / "clearcut" / "application"

STDLIB_MODULES = frozenset(sys.stdlib_module_names)
FORBIDDEN_APPLICATION_PREFIXES = (
    "flask",
    "google",
    "clickhouse_connect",
    "requests",
    "clearcut.adapters",
    "httpx",
)


def _resolve_relative_import(module: str | None, level: int, package: str) -> str:
    """The absolute dotted name a relative `from` import resolves to.

    Mirrors `importlib._bootstrap._resolve_name`: `package` is the dotted
    `__package__` of the module doing the importing. An import that walks
    above the top-level package (more dots than `package` has components)
    cannot resolve to a real module, so it is returned dotted-and-unresolved
    — never equal to a stdlib or `clearcut.domain` name, so it still shows up
    as a violation.
    """
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        return "." * level + (module or "")
    base = bits[0]
    return f"{base}.{module}" if module else base


def _imported_module_names(source: str, package: str = "") -> list[str]:
    """Every module named by `import x` or `from x import y` in `source`.

    `package` is the dotted `__package__` `source` belongs to (e.g.
    `"clearcut.domain"` for a module at `clearcut/domain/jurisdiction.py`),
    used to resolve relative (`from .x import y`) imports to their real
    absolute module.
    """
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                names.append(node.module or "")
            else:
                names.append(_resolve_relative_import(node.module, node.level, package))
    return names


def _domain_violations(source: str, package: str = "") -> list[str]:
    """Imports in `source` that are neither stdlib nor `clearcut.domain`."""
    violations = []
    for name in _imported_module_names(source, package):
        root = name.split(".")[0]
        is_domain = name == "clearcut.domain" or name.startswith("clearcut.domain.")
        if root not in STDLIB_MODULES and not is_domain:
            violations.append(name)
    return violations


def _application_violations(source: str, package: str = "") -> list[str]:
    """Imports in `source` that name a forbidden framework, client, or adapter."""
    violations = []
    for name in _imported_module_names(source, package):
        for forbidden in FORBIDDEN_APPLICATION_PREFIXES:
            if name == forbidden or name.startswith(f"{forbidden}."):
                violations.append(name)
    return violations


def _package_for(path: Path) -> str:
    """The dotted `__package__` name relative imports in the module at `path` resolve against."""
    parts = path.resolve().relative_to(REPO_ROOT / "src").with_suffix("").parts
    return ".".join(parts[:-1])


def test_domain_guard_rejects_a_flask_import():
    assert _domain_violations("import flask\n") == ["flask"]


def test_application_guard_rejects_a_flask_import():
    assert _application_violations("import flask\n") == ["flask"]


def test_application_guard_rejects_an_httpx_import():
    assert _application_violations("import httpx\n") == ["httpx"]


def test_domain_guard_resolves_a_same_package_relative_import():
    source = "from .errors import UnknownJurisdiction\n"
    assert _domain_violations(source, "clearcut.domain") == []


def test_domain_guard_rejects_a_level_escaping_relative_import():
    source = "from ..adapters import x\n"
    assert _domain_violations(source, "clearcut.domain") == ["clearcut.adapters"]


def test_domain_guard_still_accepts_a_moduleless_relative_import():
    source = "from . import errors\n"
    assert _domain_violations(source, "clearcut.domain") == []


def test_domain_modules_import_only_stdlib_or_domain():
    for path in DOMAIN_DIR.rglob("*.py"):
        violations = _domain_violations(path.read_text(), _package_for(path))
        assert violations == [], f"{path}: disallowed imports {violations}"


def test_application_modules_import_no_framework_client_or_adapter():
    for path in APPLICATION_DIR.rglob("*.py"):
        violations = _application_violations(path.read_text(), _package_for(path))
        assert violations == [], f"{path}: disallowed imports {violations}"
