"""Layer-boundary guard (AGENT.md Section 2).

`domain/` may import only the standard library or `clearcut.domain` itself.
`application/` may import `clearcut.domain`, but never a web framework, a
third-party client, or `clearcut.adapters`. `composition.py` is the single
named exception to the third rule (CP-048): it is the one place wiring
happens, and every other module under `src/clearcut/` -- outside the
`adapters/` package itself, which may reference its own siblings -- must stay
clean of `clearcut.adapters`.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src" / "clearcut"
DOMAIN_DIR = SRC_DIR / "domain"
APPLICATION_DIR = SRC_DIR / "application"
ADAPTERS_DIR = SRC_DIR / "adapters"
COMPOSITION_FILE = SRC_DIR / "composition.py"

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


def _imports_adapters(source: str, package: str = "") -> list[str]:
    """Imports in `source` naming `clearcut.adapters` or one of its submodules."""
    return [
        name
        for name in _imported_module_names(source, package)
        if name == "clearcut.adapters" or name.startswith("clearcut.adapters.")
    ]


def _adapter_import_violations(path: Path, source: str) -> list[str]:
    """The adapters imports in `source` the exclusivity gate must reject for
    the module at `path`.

    An import is allowed only when it names `path`'s own package -- the one
    legitimate case in the tree, `adapters/demo/in_memory.py`'s `from
    clearcut.adapters.demo import scenario` -- decided by comparing package
    identity through `_package_for`, never by `adapters/` membership alone
    or by relative-vs-absolute import syntax.
    """
    package = _package_for(path)
    return [name for name in _imports_adapters(source, package) if name != package]


def test_composition_imports_the_adapters_it_wires():
    """A sanity check the next test needs: if `composition.py` stopped
    importing `clearcut.adapters` altogether, the exclusivity test below
    would pass vacuously and prove nothing."""
    assert COMPOSITION_FILE.exists(), "composition.py must exist as the wiring module"
    assert _imports_adapters(COMPOSITION_FILE.read_text(), "clearcut") != []


def test_composition_is_the_only_module_importing_adapters():
    for path in SRC_DIR.rglob("*.py"):
        if path == COMPOSITION_FILE:
            continue
        violations = _adapter_import_violations(path, path.read_text())
        assert violations == [], (
            f"{path}: only composition.py may import clearcut.adapters, found {violations}"
        )


def test_same_package_absolute_adapter_import_is_allowed():
    """`in_memory.py:26`'s own line, reproduced directly: an absolute (not
    relative) same-package import must stay legal. Kills a mutant that
    whitelists by relative-import syntax instead of package identity -- that
    mutant would reject this absolute form -- and a mutant that bans every
    adapter-to-adapter import outright, which would reject it too."""
    source = "from clearcut.adapters.demo import scenario\n"
    path = ADAPTERS_DIR / "demo" / "in_memory.py"
    assert _adapter_import_violations(path, source) == []


def test_cross_package_absolute_adapter_import_is_rejected():
    """A different pair of adapter packages, same absolute-import shape as
    the allowed case above: proves the comparison is package identity, not
    merely "some `clearcut.adapters` import from inside `adapters/`" -- the
    mutant that restates today's wholesale skip one prefix narrower."""
    source = "from clearcut.adapters.bigquery import lore_store\n"
    path = ADAPTERS_DIR / "gcp" / "document_ai.py"
    assert _adapter_import_violations(path, source) == ["clearcut.adapters.bigquery"]


def test_reviewer_plant_is_now_flagged():
    """The reviewer's exact report, reproduced without touching the real
    file: `from clearcut.adapters.demo.in_memory import InMemoryTrackerStore`
    at the top of `adapters/http/routes.py`. Before this checkpoint the
    wholesale `ADAPTERS_DIR in path.parents` skip let it through and the
    suite stayed green; this pins the fix (CP-050, D39)."""
    plant = "from clearcut.adapters.demo.in_memory import InMemoryTrackerStore\n"
    path = ADAPTERS_DIR / "http" / "routes.py"
    assert _adapter_import_violations(path, plant) == ["clearcut.adapters.demo.in_memory"]


def test_gate_still_rejects_an_adapter_import_outside_adapters():
    """Regression guard: narrowing the exclusion to same-package siblings
    must not weaken the exclusivity check for modules outside `adapters/`.
    Kills a mutant that widens the same-package allowance to any importer,
    not just files under `adapters/`."""
    source = "from clearcut.adapters.demo import scenario\n"
    path = APPLICATION_DIR / "evaluate_delta.py"
    assert _adapter_import_violations(path, source) == ["clearcut.adapters.demo"]


def test_package_for_drops_only_the_module_name():
    """Pins `_package_for` (absorbed from the Backlog, D39): the narrowed
    same-package comparison runs through it, so a wrong `_package_for` would
    misclassify packages and silently let a cross-package import through.
    Kills mutant C, `".".join(parts)` in place of `".".join(parts[:-1])`,
    which survived all seven tests during CP-001's review because none of
    them routed a real path through this function."""
    assert _package_for(DOMAIN_DIR / "jurisdiction.py") == "clearcut.domain"
    assert _package_for(DOMAIN_DIR / "__init__.py") == "clearcut.domain"
