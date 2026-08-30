"""Exists to catch the `__init__.py` files under `tests/` going missing.

Paired with `tests/integration/test_basename_collision_probe.py`: same
basename, different directory. Before CP-012 added package markers under
`tests/`, pytest's rootdir import mode gave both files the same bare module
name and collecting the second raised `import file mismatch`, dropping the
whole suite to zero collected tests.
"""


def test_probe_from_unit_adapters_collects_and_runs() -> None:
    assert True
