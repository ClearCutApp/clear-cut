"""Proves `[project] dependencies` covers every third-party import under
`src/clearcut/` (CP-017).

The deliverable is this test, not the dependency list next to it: a
hand-maintained list is exactly what let `dependencies = []` survive five
adapters (AGENT.md Section 4). Every future adapter import is caught here
the moment it lands, without anyone remembering to update a second place.
"""

from __future__ import annotations

import ast
import functools
import sys
import tomllib
from dataclasses import dataclass
from importlib.metadata import Distribution, distributions
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "clearcut"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
FIRST_PARTY_TOP_LEVEL = "clearcut"
STDLIB_MODULES = frozenset(sys.stdlib_module_names)
_SPEC_MARKERS = ("==", ">=", "<=", "~=", "!=", ">", "<", "[", ";")


@dataclass(frozen=True)
class _Import:
    """One import statement's dotted module path, resolved for distribution
    matching.

    `dotted` is the most specific path the statement names: for
    `import a.b.c`, that is the statement itself. For `from a.b import c`, it
    is the guess that `c` is a submodule (`a.b.c`); `fallback` -- the `from`
    module alone -- is tried only when that guess matches no installed
    distribution, i.e. `c` was a class or function, not a submodule.
    """

    path: Path
    top_level: str
    dotted: str
    fallback: str | None = None


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
            imports.extend(
                _Import(path, alias.name.split(".")[0], alias.name) for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top_level = node.module.split(".")[0]
            imports.extend(
                _Import(path, top_level, f"{node.module}.{alias.name}", node.module)
                for alias in node.names
            )
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


def _file_parts(dist: Distribution) -> tuple[tuple[str, ...], ...]:
    return tuple(Path(str(f)).parts for f in (dist.files or ()))


@functools.cache
def _distribution_files_by_name() -> tuple[tuple[str, tuple[tuple[str, ...], ...]], ...]:
    """`(distribution name, its shipped file paths)` for every installed
    distribution, read from disk once and reused by every `_resolve` lookup."""
    return tuple(
        (dist.metadata["Name"], _file_parts(dist))
        for dist in distributions()
        if dist.metadata.get("Name")
    )


def _ships(file_parts: tuple[str, ...], dotted_parts: tuple[str, ...]) -> bool:
    """Whether a shipped file at `file_parts` makes `dotted_parts` importable:
    either a package directory (the file sits deeper, under that prefix) or a
    single-file module (same depth, same stem once the suffix is dropped)."""
    if len(file_parts) > len(dotted_parts):
        return file_parts[: len(dotted_parts)] == dotted_parts
    if len(file_parts) < len(dotted_parts):
        return False
    *dirs, leaf = file_parts
    stem = leaf.rsplit(".", 1)[0]
    return tuple(dirs) == dotted_parts[:-1] and stem == dotted_parts[-1]


@functools.cache
def _distributions_providing(dotted: str) -> tuple[str, ...]:
    """Every installed distribution that ships a module or package at `dotted`,
    found by matching its full path -- not just its top-level name -- against
    `Distribution.files`. `google` and `opentelemetry` are namespace packages
    shared by many distributions, so a top-level-only match lets declaring any
    one of them satisfy an import of any other."""
    dotted_parts = tuple(dotted.split("."))
    return tuple(
        name
        for name, files in _distribution_files_by_name()
        if any(_ships(parts, dotted_parts) for parts in files)
    )


def _resolve(imp: _Import) -> tuple[str, ...]:
    """The distribution(s) providing `imp`. Tries the specific guess first
    (`imp.dotted`); when nothing installed matches it and the statement had a
    `from` form, falls back to the module alone (`imp.fallback`), because the
    imported name may have been a class or function, not a submodule."""
    candidates = _distributions_providing(imp.dotted)
    if candidates or imp.fallback is None:
        return candidates
    return _distributions_providing(imp.fallback)


def find_undeclared_imports(root: Path, declared: set[str]) -> list[UndeclaredImport]:
    """Third-party imports under `root` whose distribution is missing from `declared`.

    An import is undeclared only when *none* of its candidate distributions
    are declared -- resolution can find more than one candidate for a shared
    namespace package. Findings are deduplicated by (file, module, candidate
    set): several submodule imports of the same undeclared distribution in
    one file produce one finding, not one per import statement.
    """
    seen: dict[tuple[Path, str, tuple[str, ...]], UndeclaredImport] = {}
    for imp in _third_party_imports(root):
        candidates = _resolve(imp)
        normalized_candidates = {_normalize(c) for c in candidates}
        if normalized_candidates & declared:
            continue
        key = (imp.path, imp.top_level, candidates)
        seen.setdefault(key, UndeclaredImport(imp.path, imp.top_level, candidates))
    return list(seen.values())


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


def _declared_minus(*names: str) -> set[str]:
    """The real declared-dependency set with the given distributions removed,
    simulating a single accidental deletion from `[project] dependencies`."""
    declared = _declared_distributions(PYPROJECT_PATH)
    excluded = {_normalize(name) for name in names}
    return declared - excluded


def _finding_for(undeclared: list[UndeclaredImport], path: Path) -> UndeclaredImport | None:
    for finding in undeclared:
        if finding.path == path:
            return finding
    return None


def test_removing_google_cloud_documentai_alone_is_caught() -> None:
    """`google` is a namespace package shared by many distributions --
    `packages_distributions()` collapses them onto one top-level key, so
    declaring `google-genai` used to silently satisfy a missing
    `google-cloud-documentai` too (CP-017, measured twice)."""
    declared = _declared_minus("google-cloud-documentai")

    undeclared = find_undeclared_imports(SRC_ROOT, declared)

    finding = _finding_for(undeclared, SRC_ROOT / "adapters" / "gcp" / "document_ai.py")
    assert finding is not None
    assert "google-cloud-documentai" in finding.candidates


def test_removing_google_genai_alone_is_caught() -> None:
    declared = _declared_minus("google-genai")

    undeclared = find_undeclared_imports(SRC_ROOT, declared)

    finding = _finding_for(undeclared, SRC_ROOT / "adapters" / "gcp" / "vertex_search.py")
    assert finding is not None
    assert "google-genai" in finding.candidates


def test_removing_google_api_core_alone_is_caught() -> None:
    declared = _declared_minus("google-api-core")

    undeclared = find_undeclared_imports(SRC_ROOT, declared)

    finding = _finding_for(undeclared, SRC_ROOT / "adapters" / "gcp" / "document_ai.py")
    assert finding is not None
    assert "google-api-core" in finding.candidates


def test_removing_parallel_web_alone_is_still_caught() -> None:
    """Reach is not lost on a distribution that already resolved correctly
    under the old top-level-only lookup."""
    declared = _declared_minus("parallel-web")

    undeclared = find_undeclared_imports(SRC_ROOT, declared)

    finding = _finding_for(undeclared, SRC_ROOT / "adapters" / "parallel" / "research.py")
    assert finding is not None
    assert "parallel-web" in finding.candidates


def test_removing_httpx_alone_is_still_caught() -> None:
    declared = _declared_minus("httpx")

    undeclared = find_undeclared_imports(SRC_ROOT, declared)

    paths = {finding.path for finding in undeclared}
    assert SRC_ROOT / "adapters" / "notify" / "webhook.py" in paths
    assert SRC_ROOT / "adapters" / "parallel" / "research.py" in paths


def test_declaring_an_unimported_dependency_reports_nothing() -> None:
    """The checker is used-to-declared only, never the reverse: a
    distribution declared in `[project] dependencies` but never imported
    from `src/` must not be flagged. CP-049's live wiring made every real
    dependency actually imported somewhere in `src/` (`composition.py` now
    imports `clickhouse-connect`, `langchain-google-community`, and
    `langchain-google-vertexai` for real), so this adds a package that
    provably is not, rather than removing a real one that used to be true
    only by omission."""
    declared = _declared_distributions(PYPROJECT_PATH) | {"a-declared-but-unused-package"}

    undeclared = find_undeclared_imports(SRC_ROOT, declared)

    assert undeclared == []


def test_import_with_no_installed_distribution_is_still_reported(tmp_path: Path) -> None:
    """An empty candidate set must still surface as a finding, not vanish
    into a vacuous intersection -- this is what will catch `clickhouse-connect`
    (CP-023), `flask` (CP-029) and the three `opentelemetry` distributions
    (CP-031) before any of them is installed."""
    scratch_module = tmp_path / "scratch_adapter.py"
    scratch_module.write_text("import definitely_not_installed_by_anything\n")

    undeclared = find_undeclared_imports(tmp_path, set())

    assert len(undeclared) == 1
    finding = undeclared[0]
    assert finding.candidates == ()
    assert "<none installed>" in str(finding)


def test_undeclared_distribution_reported_once_per_file_not_per_import() -> None:
    """`research.py` imports the `parallel-web` SDK through nine separate
    statements (`parallel`, `parallel.types.citation`, ...). Removing the one
    distribution behind all of them must produce one finding for that file,
    not one per import statement."""
    declared = _declared_minus("parallel-web")

    undeclared = find_undeclared_imports(SRC_ROOT, declared)

    hits = [
        finding
        for finding in undeclared
        if finding.path == SRC_ROOT / "adapters" / "parallel" / "research.py"
    ]
    assert len(hits) == 1
