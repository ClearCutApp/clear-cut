"""Guards the D23 adapter-error boundary (CP-034, AGENT.md Section 2).

`application/` may name a domain error but never an adapter's own module
(AGENT.md Section 2 rule 2, `tests/unit/test_layer_boundaries.py`), so every
error an adapter raises must subclass exactly one of the three types in
`domain/errors.py` -- otherwise no `application/` module could ever catch it
by name. This file enforces that two ways: a contract test that walks every
adapter module for an `Exception` subclass unclassified under the three, and
an AST guard, kept in its own file so CP-030 and CP-031 can extend
`test_layer_boundaries.py` without colliding with it, that fails if
`application/` catches `Exception` or `BaseException` -- bare, named, or
wrapped in a tuple with something narrower.
"""

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path
from types import ModuleType

import pytest

import clearcut.adapters as adapters_package
from clearcut.domain.errors import EnrichmentMissing, RecordNotFound, SourceUnavailable

REPO_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = REPO_ROOT / "src" / "clearcut" / "application"

_DOMAIN_ERROR_BASES = (RecordNotFound, SourceUnavailable, EnrichmentMissing)

# One real adapter error per domain-error base (CP-034), so the walk is
# proven to have inspected something -- membership, never a count.
_KNOWN_ADAPTER_EXCEPTIONS = {"TrackerItemNotFound", "NoGroundedSource", "NotificationFailed"}


def _adapter_modules(package: ModuleType = adapters_package) -> list[ModuleType]:
    return [
        importlib.import_module(module_info.name)
        for module_info in pkgutil.walk_packages(package.__path__, prefix=f"{package.__name__}.")
    ]


def _adapter_exception_classes() -> list[type[Exception]]:
    classes: list[type[Exception]] = []
    for module in _adapter_modules():
        for _name, candidate in inspect.getmembers(module, inspect.isclass):
            if candidate.__module__ == module.__name__ and issubclass(candidate, Exception):
                classes.append(candidate)
    return classes


def test_every_adapter_exception_subclasses_exactly_one_domain_error_type() -> None:
    unclassified = [
        cls.__qualname__
        for cls in _adapter_exception_classes()
        if sum(issubclass(cls, base) for base in _DOMAIN_ERROR_BASES) != 1
    ]
    assert unclassified == []


def test_adapter_walk_fails_loudly_on_an_unimportable_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`pkgutil.walk_packages` yields a module's `ModuleInfo` before it tries
    to import anything, and it only ever imports an entry when `ispkg` is
    true (`onerror=None` is its default, silencing that import's
    `ImportError`) -- so a broken leaf module's name always reaches
    `_adapter_modules`'s own import, and what the swallow suppresses is
    recursion into a broken package's children, never the broken module
    itself. The re-import in `_adapter_modules` is what turns that
    reached-but-unraised name into a loud failure; this pins that down."""
    package_name = f"scratch_adapters_{tmp_path.name}"
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("")
    (package_dir / "broken.py").write_text("raise ImportError('scratch adapter fails to import')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    fake_package = importlib.import_module(package_name)

    with pytest.raises(ImportError, match="scratch adapter fails to import"):
        _adapter_modules(fake_package)


def test_adapter_exception_walk_is_not_vacuously_empty() -> None:
    """`unclassified == []` above also holds if the walk found nothing --
    membership, not a count, so CP-029 adding `adapters/http/` never turns
    this red for growing correctly."""
    found = {cls.__qualname__ for cls in _adapter_exception_classes()}
    assert _KNOWN_ADAPTER_EXCEPTIONS <= found


_DISALLOWED_EXCEPT_NAMES = {"Exception", "BaseException"}

# The one place `application/` may catch broadly, named rather than inferred
# so adding a second costs a decision (ADR 0013).
#
# `StartAnalysis` runs the pipeline on a background thread. There is no caller
# left to raise to: an exception that escaped would kill the thread silently
# and leave the job row saying RUNNING until a read reaped it half an hour
# later. Catching only the domain errors would do exactly that for a bug,
# which is the failure a producer most needs told about. The catch records the
# reason on the job and stops -- it swallows nothing, it writes the failure
# down where the browser polling for it can read it.
_BROAD_CATCH_EXEMPTIONS = frozenset({"src/clearcut/application/start_analysis.py"})


def _is_disallowed_except(node: ast.ExceptHandler) -> bool:
    """True for `except:`, `except Exception`/`BaseException`, and either
    wrapped in a tuple -- every way `application/` can name nothing, or name
    something broad enough to catch everything, instead of a domain error."""
    if node.type is None:
        return True
    if isinstance(node.type, ast.Name):
        return node.type.id in _DISALLOWED_EXCEPT_NAMES
    if isinstance(node.type, ast.Tuple):
        return any(
            isinstance(elt, ast.Name) and elt.id in _DISALLOWED_EXCEPT_NAMES
            for elt in node.type.elts
        )
    return False


def _application_files_catching_disallowed_except() -> list[str]:
    violations = []
    for path in APPLICATION_DIR.rglob("*.py"):
        relative = str(path.relative_to(REPO_ROOT))
        if relative in _BROAD_CATCH_EXEMPTIONS:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_disallowed_except(node):
                violations.append(relative)
    return violations


def test_no_application_module_catches_a_bare_or_broad_exception() -> None:
    assert _application_files_catching_disallowed_except() == []


def test_the_exempt_module_is_the_only_one_that_needs_the_exemption() -> None:
    """An exemption that outlives its reason is worse than none.

    `start_analysis.py` must still contain the broad catch the exemption was
    written for. If the background worker ever stops needing it -- a durable
    queue with its own retry, say -- this fails and the exemption goes with
    it, rather than quietly widening the guard's blind spot.
    """
    exempt = REPO_ROOT / next(iter(_BROAD_CATCH_EXEMPTIONS))
    handlers = _except_handlers(exempt.read_text())

    assert any(_is_disallowed_except(node) for node in handlers)


def _except_handlers(source: str) -> list[ast.ExceptHandler]:
    return [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ExceptHandler)]


def test_bare_or_broad_except_guard_still_allows_narrow_domain_error_catches() -> None:
    handlers = _except_handlers(
        "try:\n"
        "    pass\n"
        "except EnrichmentMissing:\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except (RecordNotFound, SourceUnavailable):\n"
        "    pass\n"
    )
    assert not any(_is_disallowed_except(node) for node in handlers)
