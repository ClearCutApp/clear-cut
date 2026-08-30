"""Proves `[project] dependencies` covers every third-party import under
`src/clearcut/` (CP-017).

The deliverable is this test, not the dependency list next to it: a
hand-maintained list is exactly what let `dependencies = []` survive five
adapters (AGENT.md Section 4). Every future adapter import is caught here
the moment it lands, without anyone remembering to update a second place.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass
from importlib.metadata import packages_distributions
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "clearcut"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
FIRST_PARTY_TOP_LEVEL = "clearcut"
STDLIB_MODULES = frozenset(sys.stdlib_module_names)
_SPEC_MARKERS = ("==", ">=", "<=", "~=", "!=", ">", "<", "[", ";")


@dataclass(frozen=True)
class _Import:
    """One top-level module name imported by one file."""

    path: Path
    top_level: str


@dataclass(frozen=True)
class UndeclaredImport:
    """A third-party import whose distribution is missing from `[project] dependencies`."""

    path: Path
    top_level: str
    candidates: tuple[str, ...]

    def __str__(self) -> str:
        distributions = ", ".join(self.candidates) if self.candidates else "<none installed>"
        return (
            f"{self.path}: import {self.top_level!r} resolves to distribution(s) "
            f"[{distributions}], none of which are declared in [project] dependencies"
        )


def _module_imports(path: Path) -> list[_Import]:
    """Every top-level module named by an `import` or `from` in `path`.

    A relative `from .x import y` (`level > 0`) always resolves inside the
    package doing the importing, so it can never name a third-party
    distribution and is skipped outright rather than resolved.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    imports: list[_Import] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(_Import(path, alias.name.split(".")[0]) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append(_Import(path, node.module.split(".")[0]))
    return imports


def _all_imports(root: Path) -> list[_Import]:
    imports: list[_Import] = []
    for path in sorted(root.rglob("*.py")):
        imports.extend(_module_imports(path))
    return imports


def _is_stdlib(top_level: str) -> bool:
    return top_level in STDLIB_MODULES


def _is_first_party(top_level: str) -> bool:
    return top_level == FIRST_PARTY_TOP_LEVEL


def _third_party_imports(root: Path) -> list[_Import]:
    return [
        imp
        for imp in _all_imports(root)
        if not _is_stdlib(imp.top_level) and not _is_first_party(imp.top_level)
    ]


def _normalize(distribution_name: str) -> str:
    """PEP 503 normalization, so `google_genai` and `Google-GenAI` compare equal."""
    return distribution_name.strip().lower().replace("_", "-")


def _distribution_name(requirement: str) -> str:
    name = requirement
    for marker in _SPEC_MARKERS:
        name = name.split(marker)[0]
    return name.strip()


def _declared_distributions(pyproject_path: Path) -> set[str]:
    data = tomllib.loads(pyproject_path.read_text())
    dependencies = data["project"]["dependencies"]
    return {_normalize(_distribution_name(dep)) for dep in dependencies}


def find_undeclared_imports(root: Path, declared: set[str]) -> list[UndeclaredImport]:
    """Third-party imports under `root` whose distribution is missing from `declared`.

    A top-level import name can resolve to more than one distribution
    (`google` is a shared namespace package: `google-genai`,
    `google-cloud-documentai`, and over a dozen others all install modules
    under it), so an import is undeclared only when *none* of its candidate
    distributions are declared.
    """
    distributions_by_module = packages_distributions()
    undeclared: list[UndeclaredImport] = []
    for imp in _third_party_imports(root):
        candidates = tuple(distributions_by_module.get(imp.top_level, ()))
        normalized_candidates = {_normalize(c) for c in candidates}
        if not normalized_candidates & declared:
            undeclared.append(UndeclaredImport(imp.path, imp.top_level, candidates))
    return undeclared


def test_every_third_party_import_in_src_is_declared() -> None:
    declared = _declared_distributions(PYPROJECT_PATH)
    undeclared = find_undeclared_imports(SRC_ROOT, declared)
    assert undeclared == [], "\n".join(str(u) for u in undeclared)


def test_stdlib_and_first_party_imports_are_excluded_not_ignored() -> None:
    """The exclusion is asserted, not assumed: prove stdlib and `clearcut.*`
    imports are actually present and actually filtered, not merely absent."""
    top_levels = {imp.top_level for imp in _all_imports(SRC_ROOT)}
    stdlib_seen = {t for t in top_levels if _is_stdlib(t)}
    first_party_seen = {t for t in top_levels if _is_first_party(t)}

    assert stdlib_seen, "expected at least one stdlib import under src/clearcut/"
    assert first_party_seen, "expected at least one clearcut.* import under src/clearcut/"

    third_party = _third_party_imports(SRC_ROOT)
    assert not any(_is_stdlib(imp.top_level) for imp in third_party)
    assert not any(_is_first_party(imp.top_level) for imp in third_party)


def test_check_is_non_vacuous_and_names_the_offending_module(tmp_path: Path) -> None:
    """Adding one undeclared third-party import to a scratch module must fail,
    naming that module -- proof the check above can actually catch a miss."""
    scratch_module = tmp_path / "scratch_adapter.py"
    scratch_module.write_text("import yaml\n")
    declared = _declared_distributions(PYPROJECT_PATH)

    undeclared = find_undeclared_imports(tmp_path, declared)

    assert len(undeclared) == 1
    finding = undeclared[0]
    assert finding.path == scratch_module
    assert finding.top_level == "yaml"
    assert "PyYAML" in finding.candidates


def test_python_312_classifier_sits_next_to_the_dependencies() -> None:
    data = tomllib.loads(PYPROJECT_PATH.read_text())
    project = data["project"]

    assert "Programming Language :: Python :: 3.12" in project.get("classifiers", [])
    assert project["requires-python"] == ">=3.11"
