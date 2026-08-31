"""Guards the D23 adapter-error boundary (CP-034, AGENT.md Section 2).

`application/` may name a domain error but never an adapter's own module
(AGENT.md Section 2 rule 2, `tests/unit/test_layer_boundaries.py`), so every
error an adapter raises must subclass exactly one of the three types in
`domain/errors.py` -- otherwise no `application/` module could ever catch it
by name. This file enforces that two ways: a contract test that walks every
adapter module for an `Exception` subclass unclassified under the three, and
an AST guard, kept in its own file so CP-030 and CP-031 can extend
`test_layer_boundaries.py` without colliding with it, that fails if
`application/` catches a bare `Exception`.
"""

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path
from types import ModuleType

import clearcut.adapters as adapters_package
from clearcut.domain.errors import EnrichmentMissing, RecordNotFound, SourceUnavailable

REPO_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_DIR = REPO_ROOT / "src" / "clearcut" / "application"

_DOMAIN_ERROR_BASES = (RecordNotFound, SourceUnavailable, EnrichmentMissing)


def _adapter_modules() -> list[ModuleType]:
    return [
        importlib.import_module(module_info.name)
        for module_info in pkgutil.walk_packages(
            adapters_package.__path__, prefix=f"{adapters_package.__name__}."
        )
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


def _application_files_catching_bare_exception() -> list[str]:
    violations = []
    for path in APPLICATION_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            is_bare_exception = isinstance(node, ast.ExceptHandler) and (
                isinstance(node.type, ast.Name) and node.type.id == "Exception"
            )
            if is_bare_exception:
                violations.append(str(path.relative_to(REPO_ROOT)))
    return violations


def test_no_application_module_catches_a_bare_exception() -> None:
    assert _application_files_catching_bare_exception() == []
