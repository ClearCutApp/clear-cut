"""Behaviour tests for infra/fetch_legal_corpus.py.

The corpus was populated by hand, which is why six of eight categories ground
against nothing: nobody hand-sources ten jurisdictions. Parallel is already in
this stack to search the live web (ADR 0003), and finding a statute is that
same job.

The sharp test here is `is_official`. What this script downloads becomes what
`LegalGrounding` cites to a producer deciding whether to clear a scene, and a
citation pointing at a law-firm blog is worse than no citation because it looks
authoritative and is not.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from clearcut.domain.finding import Category

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "fetch_legal_corpus.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_legal_corpus", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
        check=False,
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.argentina.gob.ar/normativa/nacional/ley-11723",
        "https://www.senado.gob.ar/parlamentario/x.pdf",
        "https://www.oas.org/juridico/PDFs/arg_ley11723.pdf",
        "https://www.wipo.int/wipolex/es/text.pdf",
        "https://www.gov.uk/guidance/filming",
    ],
)
def test_official_sources_are_accepted(url: str) -> None:
    assert load_script().is_official(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://lbucciabogados.com.ar/Ley-de-Marcas-22362.pdf",
        "https://es.wikipedia.org/wiki/Ley_11723",
        "https://medium.com/@someone/argentine-copyright",
        "https://jurisprudenciaarg.com/leyes/23208",
    ],
)
def test_unofficial_sources_are_rejected(url: str) -> None:
    """A real URL from an earlier search, and three of the shape that follows it.

    `lbucciabogados.com.ar` genuinely hosts a copy of Ley 22.362 and came back
    in a live search. It is a law firm. Its copy may even be accurate, and it
    is still not what a clearance citation should point at.
    """
    assert not load_script().is_official(url)


def test_a_path_segment_cannot_smuggle_an_official_suffix() -> None:
    """The check reads the host, not the whole URL.

    Without that, `evil.com/www.gob.ar/ley.pdf` passes a naive substring test
    and puts an attacker-controlled document into a legal corpus.
    """
    assert not load_script().is_official("https://evil.example/www.argentina.gob.ar/ley.pdf")
    assert not load_script().is_official("https://gob.ar.evil.example/ley.pdf")


def test_every_category_that_grounds_has_a_search_subject() -> None:
    subjects = load_script().CATEGORY_SUBJECTS
    for category in Category:
        if category in (Category.CONTINUITY, Category.POLICY):
            continue
        assert subjects[category].strip()
        assert category.value not in subjects[category]


def test_the_objective_names_the_jurisdiction_and_the_subject() -> None:
    module = load_script()
    objective = module.search_objective("Argentina", Category.SPECIAL_SYMBOLS)

    assert "Argentina" in objective
    assert "national symbols" in objective


def test_dry_run_issues_no_search_and_needs_no_key() -> None:
    result = run("AR", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "argentina/" in result.stdout
    assert "no search issued" in result.stdout
    assert "PARALLEL_API_KEY" not in result.stderr


def test_a_real_run_without_the_key_exits_naming_it() -> None:
    result = run("AR")

    assert result.returncode != 0
    assert "PARALLEL_API_KEY" in result.stderr


def test_an_unknown_jurisdiction_is_refused() -> None:
    result = run("ZZ", "--dry-run")

    assert result.returncode != 0
    assert "ZZ" in result.stderr


def test_a_missing_jurisdiction_argument_is_refused() -> None:
    result = run("--dry-run")

    assert result.returncode != 0
    assert "JURISDICTION_CODE" in result.stderr
