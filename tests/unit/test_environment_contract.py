"""Bidirectional guard: the environment `_required_env` reads in
`composition.py` and the environment `.env.example` and
`docs/plan/infrastructure.md` section 8 document are the same set
(CP-051, Decision D40).

Hand-copying the required set into two documents is exactly the failure this
checkpoint exists to fix: `composition.py` grew a tenth `_required_env` call
(`VERTEX_SEARCH_DATA_STORE_ID`) that neither document ever recorded, while
`.env.example` and the doc table both still carried `AGENT_BUILDER_AGENT_ID`,
which nothing under `src/` reads. The fix parses the required set out of
`composition.py` itself on every run, the same technique
`test_declared_dependencies.py` and `test_layer_boundaries.py` already use
for `src/` imports, so a future call site can drift only by first editing
this test.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSITION_PATH = REPO_ROOT / "src" / "clearcut" / "composition.py"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
INFRASTRUCTURE_DOC_PATH = REPO_ROOT / "docs" / "plan" / "infrastructure.md"

_REQUIRED_ENV_FUNC = "_required_env"
_ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=")
_DOC_TABLE_ROW = re.compile(r"^\|\s*`([A-Z][A-Z0-9_]*)`\s*\|")
_SECTION_8_HEADING = "## 8. Secrets and configuration"

# Read by the OTLP exporters themselves, never by our code (CP-031 criterion
# 1; CP-049's attempt-1 ruling), or read via os.environ.get with a live-mode
# default rather than _required_env (CLEARCUT_MODE, composition.py's own
# mode switch, CP-052), or read only outside the running application -- by
# infra/provision_grafana_dashboard.py and tests/live/test_grafana_receipt_live.py
# (GRAFANA_URL, GRAFANA_TOKEN, CP-058) -- documented but deliberately not
# required. The service starts and serves without every name in this set.
OPTIONAL_ENV_VARS = frozenset(
    {
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_HEADERS",
        "CLEARCUT_MODE",
        "GRAFANA_URL",
        "GRAFANA_TOKEN",
    }
)


def _required_env_names(source: str) -> set[str]:
    """Every literal name passed to `_required_env(...)` in `source`, read
    from the AST rather than grepped, so the check survives a reordering or
    reformatting of the call sites."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == _REQUIRED_ENV_FUNC
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value)
    return names


def _env_example_names(text: str) -> set[str]:
    """Every variable name assigned in an `.env`-shaped file."""
    return {m.group(1) for line in text.splitlines() if (m := _ENV_LINE.match(line))}


def _section_8_table_names(text: str) -> set[str]:
    """Every backtick-quoted variable name in the first column of the
    Markdown table under `## 8. Secrets and configuration`, stopping at the
    next `## ` heading."""
    lines = text.splitlines()
    start = lines.index(_SECTION_8_HEADING) + 1
    names: set[str] = set()
    for line in lines[start:]:
        if line.startswith("## "):
            break
        match = _DOC_TABLE_ROW.match(line)
        if match:
            names.add(match.group(1))
    return names


def _mismatches(required: set[str], documented: set[str]) -> tuple[set[str], set[str]]:
    """`(missing, undocumented)`: required names absent from `documented`,
    and documented names -- other than `OPTIONAL_ENV_VARS` -- that nothing
    requires."""
    missing = required - documented
    undocumented = documented - required - OPTIONAL_ENV_VARS
    return missing, undocumented


def test_required_env_names_match_env_example() -> None:
    required = _required_env_names(COMPOSITION_PATH.read_text())
    documented = _env_example_names(ENV_EXAMPLE_PATH.read_text())

    missing, undocumented = _mismatches(required, documented)

    assert missing == set(), f"required by composition.py, missing from .env.example: {missing}"
    assert undocumented == set(), f"in .env.example, but nothing requires it: {undocumented}"


def test_required_env_names_match_infrastructure_doc_table() -> None:
    required = _required_env_names(COMPOSITION_PATH.read_text())
    documented = _section_8_table_names(INFRASTRUCTURE_DOC_PATH.read_text())

    missing, undocumented = _mismatches(required, documented)

    assert missing == set(), (
        f"required by composition.py, missing from infrastructure.md section 8: {missing}"
    )
    assert undocumented == set(), (
        f"in infrastructure.md section 8, but nothing requires it: {undocumented}"
    )


def test_a_new_required_variable_is_caught_before_it_is_documented(tmp_path: Path) -> None:
    """The drift that produced this checkpoint, reproduced: a throwaway copy
    of `composition.py` grows one more `_required_env` call for a variable
    neither document has ever heard of. The guard has to fail in this
    direction too, not only in today's already-fixed state."""
    scratch = tmp_path / "composition_scratch.py"
    scratch.write_text(COMPOSITION_PATH.read_text() + '\n_required_env("CLEARCUT_UNDOCUMENTED")\n')

    required = _required_env_names(scratch.read_text())
    documented = _env_example_names(ENV_EXAMPLE_PATH.read_text())

    missing, _ = _mismatches(required, documented)

    assert missing == {"CLEARCUT_UNDOCUMENTED"}


def test_a_documented_but_unread_variable_is_caught() -> None:
    """The reverse direction, which is the half `AGENT_BUILDER_AGENT_ID` came
    through: a name planted in `.env.example` that nothing under `src/`
    reads must fail, unless it is named in `OPTIONAL_ENV_VARS`."""
    required = _required_env_names(COMPOSITION_PATH.read_text())
    documented = _env_example_names(ENV_EXAMPLE_PATH.read_text()) | {"CLEARCUT_FABRICATED"}

    _, undocumented = _mismatches(required, documented)

    assert undocumented == {"CLEARCUT_FABRICATED"}


def test_the_grafana_credentials_are_documented_though_no_adapter_reads_them() -> None:
    """`OPTIONAL_ENV_VARS` only *permits* a name to sit in the documents; it
    does not keep it there. `GRAFANA_URL` and `GRAFANA_TOKEN` are read by
    `infra/provision_grafana_dashboard.py` and the CP-058 live receipt, never
    by `composition.py`, so `_required_env` cannot carry them and nothing else
    would notice if both documents dropped them. CP-058's entire remaining
    action is a human setting these two, so the instruction needs somewhere to
    live."""
    grafana = {"GRAFANA_URL", "GRAFANA_TOKEN"}

    assert grafana <= _env_example_names(ENV_EXAMPLE_PATH.read_text())
    assert grafana <= _section_8_table_names(INFRASTRUCTURE_DOC_PATH.read_text())
    assert grafana <= OPTIONAL_ENV_VARS
