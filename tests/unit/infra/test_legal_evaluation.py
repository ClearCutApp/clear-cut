import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from infra.deployed_acceptance import Response, canonical, digest
from infra.evaluate_legal_coverage import (
    GAP_TEXT,
    ROOT,
    Corpus,
    Evaluation,
    cases_from,
    local_case,
)
from infra.ingest_legal_corpus import encode, sources

from clearcut.application.ports import GroundedAnswer
from clearcut.domain.finding import Citation

STORE = "projects/test-project/locations/global/collections/default_collection/dataStores/legal"


def fixture(directory: Path):
    manifest = json.loads((ROOT / "legal-sources-2026-09-06.json").read_bytes())
    cases = cases_from(json.loads((ROOT / "legal-evaluation-cases-2026-09-06.json").read_bytes()))
    entries = {}
    for source in sources(manifest):
        text = (
            "Synthetic source fixture passage for "
            + source["id"]
            + "; reproductions and limitations are recorded for this test only."
        ).encode()
        original = b"original fixture " + text
        (directory / (source["id"] + ".txt")).write_bytes(text)
        (directory / (source["id"] + ".original")).write_bytes(original)
        entries[source["id"]] = {
            "text_sha256": digest(text),
            "original_sha256": digest(original),
            "document": {
                "content": {"uri": "gs://corpus/" + source["id"] + ".txt"},
                "structData": {
                    "source_url": source["url"],
                    "jurisdiction": source["jurisdiction"],
                    "original_sha256": digest(original),
                    "text_sha256": digest(text),
                },
            },
        }
    receipt = {
        "status": "imported_readback_verified",
        "sources": entries,
        "identity": {
            "manifest_sha256": digest(encode(manifest)),
            "target": STORE,
            "bucket": "corpus",
        },
    }
    (directory / "receipt.json").write_bytes(encode(receipt))
    return manifest, cases, Corpus(manifest, directory, STORE)


def answer_for(case: dict[str, Any], corpus: Corpus, **changes: Any) -> GroundedAnswer:
    record = corpus.documents[case["expected_source"]]
    citation = {"uri": record["uri"], "title": "Synthetic citation", "snippet": record["text"]}
    citation.update(changes)
    return GroundedAnswer(
        "Unassessed generated answer about the synthetic fixture.", (Citation(**citation),)
    )


def test_actual_twelve_cases_all_have_one_national_and_one_local_case():
    value = json.loads((ROOT / "legal-evaluation-cases-2026-09-06.json").read_bytes())
    assert len(cases_from(value)) == 12
    value["cases"].pop()
    with pytest.raises(ValueError):
        cases_from(value)


def test_gcs_citation_maps_to_verified_expected_official_source_without_legal_pass(tmp_path):
    _, cases, corpus = fixture(tmp_path)
    result = corpus.check(cases[0], answer_for(cases[0], corpus))
    assert result["status"] == "structural_verified"
    assert result["citations"][0]["official_url"] == cases[0]["expected_source"]
    assert result["semantic_assessment"] == "unverified" and result["legal_clearance"] is False


@pytest.mark.parametrize("failure", ["fabricated", "wrong-country", "foreign-uri", "tiny"])
def test_matching_uri_alone_or_wrong_jurisdiction_never_proves_grounding(tmp_path, failure):
    _, cases, corpus = fixture(tmp_path)
    case = cases[0]
    answer = answer_for(case, corpus)
    if failure == "fabricated":
        answer = answer_for(
            case, corpus, snippet="Invented passage not present in the source. " * 3
        )
    elif failure == "tiny":
        answer = answer_for(case, corpus, snippet="Synthetic")
    elif failure == "foreign-uri":
        answer = answer_for(case, corpus, uri="https://wrong.example/source")
    else:
        answer = answer_for(cases[2], corpus)
    with pytest.raises(ValueError):
        corpus.check(case, answer)


@pytest.mark.parametrize("changed", ["source", "target", "manifest"])
def test_corpus_rejects_modified_preserved_bytes_or_identity(tmp_path, changed):
    manifest, _, _ = fixture(tmp_path)
    if changed == "source":
        (tmp_path / "argentina-copyright.txt").write_bytes(b"substituted")
    if changed == "manifest":
        manifest["date"] = "changed"
    with pytest.raises(ValueError):
        Corpus(manifest, tmp_path, STORE + "-other" if changed == "target" else STORE)


class Grounder:
    def __init__(self, answer: GroundedAnswer, fail: bool = False) -> None:
        self.answer, self.fail, self.calls = answer, fail, 0

    def ground(self, query: str, jurisdiction: Any) -> GroundedAnswer:
        self.calls += 1
        if self.fail:
            raise TimeoutError("private provider detail")
        return self.answer


class LocalTransport:
    def __init__(self, case: dict[str, Any]) -> None:
        self.case = case
        self.mutations: list[tuple[str, dict[str, Any] | None]] = []
        self.tracker = [{"item_id": "item-1", "state": "BLOCKED", "version": 1}]
        self.change_tracker = False
        self.answer = {"text": GAP_TEXT, "citations": []}

    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        body: dict[str, Any] | None = None,
        file: bytes | None = None,
    ) -> Response:
        if method == "POST":
            self.mutations.append((path, body))
            assert path.endswith("/questions")
            assert body == {
                "question": self.case["question"],
                "jurisdiction_code": self.case["jurisdiction"],
            }
            if self.change_tracker:
                self.tracker[0]["state"] = "CLEARED"
            return Response(200, canonical(self.answer))
        if path.endswith("/settings"):
            value: Any = {
                "title": "Synthetic legal evaluation run",
                "version": 1,
                "jurisdiction_code": self.case["jurisdiction"],
                "locations": [
                    {"country": loc["country_code"], "location": loc["location"]}
                    for loc in self.case["production_locations"]
                ],
            }
        elif path.endswith("/local-research"):
            value = {"configured": True, "research": []}
        else:
            assert path.endswith("/tracker-items")
            value = self.tracker
        return Response(200, canonical(value))


def test_local_cases_check_exact_gap_and_readback_without_tracker_mutation(tmp_path):
    _, cases, _ = fixture(tmp_path)
    case = cases[1]
    transport = LocalTransport(case)
    result = local_case(
        case, {"project_id": "project-1", "title": "Synthetic legal evaluation run"}, transport
    )
    assert result["status"] == "structural_verified"
    assert len(transport.mutations) == 1 and transport.mutations[0][0].endswith("/questions")
    transport.change_tracker = True
    with pytest.raises(ValueError, match="mutated_tracker"):
        local_case(
            case, {"project_id": "project-1", "title": "Synthetic legal evaluation run"}, transport
        )


def test_local_response_uses_real_application_route_and_no_national_fallback(tmp_path):
    from flask import Flask

    from clearcut.adapters.http.questions import create_questions_blueprint
    from clearcut.application.answer_project_question import AnswerProjectQuestion
    from clearcut.application.local_research_answer import LocalResearchAnswer

    _, cases, _ = fixture(tmp_path)
    case = cases[1]
    local = LocalResearchAnswer(
        SimpleNamespace(get=lambda project: SimpleNamespace(version=1)),
        SimpleNamespace(list=lambda project: []),
    )
    # Any accidental national/lore/tracker fallback raises because these ports have no methods.
    # Four positional ports named one by one: an unpacked generator hides its
    # length from mypy, which then reads `local` as a possible duplicate.
    application = AnswerProjectQuestion(
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        local=local,
    )
    app = Flask(__name__)
    app.register_blueprint(create_questions_blueprint(application))
    client = app.test_client()

    class RealLocalTransport(LocalTransport):
        def request(self, method: str, path: str, **kwargs: Any) -> Response:
            if method == "POST":
                result = client.post(path, json=kwargs["body"])
                return Response(result.status_code, result.data, result.content_type)
            return super().request(method, path, **kwargs)

    result = local_case(
        case,
        {"project_id": "project-1", "title": "Synthetic legal evaluation run"},
        RealLocalTransport(case),
    )
    assert result["status"] == "structural_verified"


@pytest.mark.parametrize("change", ["target", "providers", "source_hash"])
def test_resume_rejects_changed_bindings(tmp_path, change):
    _, cases, _ = fixture(tmp_path)
    binding = {"target": "target", "providers": {"model": "model"}, "source_hash": "source"}
    Evaluation(tmp_path, cases, binding)
    altered = deepcopy(binding)
    altered[change] = "changed"
    with pytest.raises(ValueError, match="binding_changed"):
        Evaluation(tmp_path, cases, altered)


@pytest.mark.parametrize("interrupted", [False, True])
def test_completed_or_interrupted_external_call_is_not_repeated_and_all_cases_accounted(
    tmp_path, interrupted
):
    _, cases, corpus = fixture(tmp_path)
    grounder = Grounder(answer_for(cases[0], corpus), fail=interrupted)
    run = Evaluation(tmp_path, cases, {"model": "frozen"})
    result = run.execute(cases[0]["id"], corpus, grounder, {}, LocalTransport(cases[1]))
    assert result["total_cases"] == 12
    expected = "call_outcome_unknown" if interrupted else "structural_verified"
    assert result["cases"][cases[0]["id"]] == expected
    run = Evaluation(tmp_path, cases, {"model": "frozen"})
    run.execute(cases[0]["id"], corpus, grounder, {}, LocalTransport(cases[1]))
    assert grounder.calls == 1
    assert "private provider detail" not in (tmp_path / "evaluation.json").read_text()
