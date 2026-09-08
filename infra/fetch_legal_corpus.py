#!/usr/bin/env python3
"""Discover official-source candidates with Parallel; never ingest unreviewed results.

`gs://clearcut-legal-corpus/` was populated by hand, which is why six of the
eight clearance categories ground against nothing: nobody was going to
hand-source ten jurisdictions. Parallel is already in this stack to search the
live web (ADR 0003), and finding a statute is that same job.

The corpus is what `LegalGrounding` cites to a producer, so this script trusts
only official sources. A URL that is not on a government or
intergovernmental domain is rejected rather than downloaded: a clearance
citation pointing at a law-firm blog is worse than no citation, because it
looks authoritative and is not.

Usage:
    .venv/bin/python infra/fetch_legal_corpus.py AR [--dry-run]

--dry-run prints the searches it would run and the terms behind each, and makes
no network call, so it needs no key. A real run needs `PARALLEL_API_KEY` and
prints candidates only. Use ingest_legal_corpus.py for reviewed ingestion.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from clearcut.domain.finding import Category
    from clearcut.domain.jurisdiction import jurisdiction_for
except ModuleNotFoundError as exc:  # pragma: no cover - depends on the interpreter
    print(f"fetch_legal_corpus.py: {exc.name} is not importable.", file=sys.stderr)
    raise SystemExit(1) from exc

REQUIRED = ("PARALLEL_API_KEY",)

SEARCH_URL = "https://api.parallel.ai/v1/search"

# Only these suffixes are accepted. Anything else is discarded with a reason.
# `.gob`/`.gov` cover national and state publishers, and the two
# intergovernmental bodies publish authoritative consolidated texts that a
# national site sometimes does not offer as a PDF.
OFFICIAL_SUFFIXES = (
    ".gob.ar",
    ".gov",
    ".gob.mx",
    ".gob.es",
    "boe.es",
    ".gov.co",
    "comunidadandina.org",
    ".gouv.fr",
    ".gov.uk",
    ".gov.in",
    ".gov.br",
    ".go.kr",
    ".gc.ca",
    "wipo.int",
    "oas.org",
)

# What statute to look for, per category. Mirrors
# `application/grounding_query.py`'s terms, in the language of the search rather
# than of the corpus: this asks a search engine, not a data store.
CATEGORY_SUBJECTS: dict[Category, str] = {
    Category.INDUSTRIAL_PROPERTY: "trademark and brand registration law",
    Category.COPYRIGHT_WORKS: "copyright and authors' rights law",
    Category.PERSONALITY_IMAGE: "personality rights, image and likeness law",
    Category.INTEGRATED_VISUAL: "artistic works and design protection law",
    Category.LOCATIONS_PERMITS: "film production location permit regulations",
    Category.SPECIAL_SYMBOLS: "use of national symbols, flag and emblems law",
}


def is_official(url: str) -> bool:
    """Whether a URL is on a domain this corpus will cite.

    Checked against the host, not the whole URL, so a path segment cannot
    smuggle an official-looking suffix past it.
    """
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443):
            return False
    except ValueError:
        return False
    return any(
        host == suffix.lstrip(".") or host.endswith("." + suffix.lstrip("."))
        for suffix in OFFICIAL_SUFFIXES
    )


def search_objective(jurisdiction_name: str, category: Category) -> str:
    return (
        f"Find the official full text of {jurisdiction_name}'s "
        f"{CATEGORY_SUBJECTS[category]}, as a PDF on a government website."
    )


def _missing_credentials() -> list[str]:
    return [name for name in REQUIRED if not os.environ.get(name, "").strip()]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in args
    positional = [arg for arg in args if not arg.startswith("--")]
    unknown = [arg for arg in args if arg.startswith("--") and arg != "--dry-run"]
    if unknown or len(positional) != 1:
        print(f"usage: {Path(__file__).name} <JURISDICTION_CODE> [--dry-run]", file=sys.stderr)
        return 2

    try:
        jurisdiction = jurisdiction_for(positional[0].upper())
    except Exception as exc:
        print(f"fetch_legal_corpus.py: {exc}", file=sys.stderr)
        return 2

    print(f"corpus prefix: gs://clearcut-legal-corpus/{jurisdiction.corpus_prefix}")
    for category in CATEGORY_SUBJECTS:
        print(f"  {category.value}: {search_objective(jurisdiction.display_name, category)}")

    if dry_run:
        print("\n--dry-run: no search issued, nothing downloaded, nothing uploaded.")
        return 0

    missing = _missing_credentials()
    if missing:
        print(
            f"fetch_legal_corpus.py: missing required environment {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    import httpx

    api_key = os.environ["PARALLEL_API_KEY"]
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=5.0)) as http:
        for category in CATEGORY_SUBJECTS:
            objective = search_objective(jurisdiction.display_name, category)
            response = http.post(
                SEARCH_URL,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "objective": objective,
                    "search_queries": [
                        f"{jurisdiction.display_name} {CATEGORY_SUBJECTS[category]} pdf",
                    ],
                },
            )
            if not response.is_success:
                print(f"  {category.value}: search failed {response.status_code}", file=sys.stderr)
                continue
            urls = [r.get("url", "") for r in response.json().get("results", [])]
            official = [url for url in urls if is_official(url)]
            rejected = [url for url in urls if not is_official(url)]
            for url in official:
                print(f"  {category.value}: candidate {url}")
            for url in rejected:
                print(f"  {category.value}: rejected, not an official domain: {url}")
            if not official:
                print(f"  {category.value}: no official source found", file=sys.stderr)
    print(
        "\nCandidates printed, not uploaded. Review them, then upload with "
        "`gcloud storage cp` and re-run infra/build_manifest.py."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
