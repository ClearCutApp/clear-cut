"""One-case-at-a-time legal evidence collection; structural proof is not legal advice.

The default prints the twelve-case plan without network calls. --execute records
one bounded provider/application result. Interrupted calls never repeat automatically.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

from clearcut.application.ports import GroundedAnswer
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.provider_config import ProviderConfig
from infra.deployed_acceptance import HttpTransport, Transport, digest, identifier, require
from infra.ingest_legal_corpus import encode, sources

ROOT = Path(__file__).resolve().parent.parent / "docs/recovery"
COUNTRIES = {"AR", "MX", "ES", "CO", "US", "CA"}
GAP_TEXT = (
    "Local coverage gap: no matching official research is recorded for this question "
    "and the current production locations. Exact permit requirements, issuing "
    "authority and fees remain unknown. Save the locations and research this "
    "question in Production settings. National statutes do not establish local permission."
)


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def cases_from(value: dict[str, Any]) -> list[dict[str, Any]]:
    cases = value["cases"]
    require(
        len(cases) == 12 and len({case["id"] for case in cases}) == 12,
        "exact_twelve_unique_cases_required",
    )
    require(
        {(case["jurisdiction"], case["kind"]) for case in cases}
        == {
            (country, kind)
            for country in COUNTRIES
            for kind in ("national-grounding", "unsupported-local")
        },
        "case_coverage_mismatch",
    )
    for case in cases:
        identifier(case["id"])
        require(
            isinstance(case["question"], str) and 0 < len(case["question"]) <= 4000,
            "invalid_case_question",
        )
    return list(cases)


class Corpus:
    """Only hash-verified, read-back ingestion documents can support a citation."""

    def __init__(self, manifest: dict[str, Any], directory: Path, data_store: str) -> None:
        receipt = json.loads((directory / "receipt.json").read_bytes())
        require(receipt["status"] == "imported_readback_verified", "ingestion_not_verified")
        require(
            receipt["identity"]["manifest_sha256"] == digest(encode(manifest))
            and receipt["identity"]["target"] == data_store,
            "ingestion_target_or_manifest_changed",
        )
        self.documents: dict[str, dict[str, Any]] = {}
        self.receipt_hash = digest(encode(receipt))
        for source in sources(manifest):
            entry = receipt["sources"][source["id"]]
            original_path = directory / (source["id"] + ".original")
            text_path = directory / (source["id"] + ".txt")
            require(
                original_path.stat().st_size <= 25 * 1024 * 1024
                and text_path.stat().st_size <= 25 * 1024 * 1024,
                "source_exceeds_limit",
            )
            original, text = original_path.read_bytes(), text_path.read_bytes()
            require(
                digest(original) == entry["original_sha256"]
                and digest(text) == entry["text_sha256"],
                "source_bytes_changed",
            )
            document = entry["document"]
            metadata = document["structData"]
            require(
                metadata["source_url"] == source["url"]
                and metadata["jurisdiction"] == source["jurisdiction"]
                and metadata["original_sha256"] == entry["original_sha256"]
                and metadata["text_sha256"] == entry["text_sha256"],
                "source_metadata_changed",
            )
            uri = document["content"]["uri"]
            require(
                uri.startswith("gs://" + receipt["identity"]["bucket"] + "/"),
                "source_bucket_mismatch",
            )
            record = {
                "source": source,
                "text": normalized(text.decode("utf-8")),
                "text_sha256": entry["text_sha256"],
                "uri": uri,
            }
            for alias in (uri, source["url"]):
                require(alias not in self.documents, "ambiguous_source_mapping")
                self.documents[alias] = record

    def check(self, case: dict[str, Any], answer: GroundedAnswer) -> dict[str, Any]:
        require(
            bool(answer.text.strip()) and len(answer.text) <= 40000, "answer_missing_or_oversize"
        )
        require(0 < len(answer.citations) <= 30, "vertex_citations_required")
        matched_expected = False
        verified = []
        for citation in answer.citations:
            record = self.documents.get(citation.uri)
            require(record is not None, "citation_source_unknown")
            assert record is not None
            require(
                record["source"]["jurisdiction"]
                == jurisdiction_for(case["jurisdiction"]).corpus_prefix.rstrip("/"),
                "citation_wrong_jurisdiction",
            )
            snippet = normalized(citation.snippet)
            # A URI alone, guessed quotation, or generic tiny phrase proves no passage.
            require(
                40 <= len(snippet) <= 12000 and snippet in record["text"],
                "citation_passage_not_in_preserved_source",
            )
            matched_expected |= record["source"]["url"] == case["expected_source"]
            verified.append(
                {
                    "official_url": record["source"]["url"],
                    "uri": citation.uri,
                    "source_sha256": record["text_sha256"],
                    "snippet": citation.snippet,
                }
            )
        require(matched_expected, "expected_official_source_not_cited")
        return {
            "status": "structural_verified",
            "provider": "vertex_search",
            "answer": answer.text,
            "citations": verified,
            "semantic_assessment": "unverified",
            "legal_clearance": False,
        }


class Grounder(Protocol):
    def ground(self, query: str, jurisdiction: Any) -> GroundedAnswer: ...


def read(transport: Transport, path: str, authenticated: bool = True) -> Any:
    response = transport.request("GET", path, authenticated=authenticated)
    require(response.status == 200, "application_read_unavailable")
    return response.json()


def local_case(
    case: dict[str, Any], binding: dict[str, str], transport: Transport
) -> dict[str, Any]:
    """Observe a configured synthetic project; never modify production settings/tracker."""
    project_id = identifier(binding["project_id"])
    path = "/api/projects/" + quote(project_id, safe="")
    settings = read(transport, path + "/settings")
    expected_locations = [
        {"country": loc["country_code"], "location": loc["location"]}
        for loc in case["production_locations"]
    ]
    require(
        binding["title"].startswith("Synthetic legal evaluation ")
        and settings["title"] == binding["title"]
        and settings["jurisdiction_code"] == case["jurisdiction"]
        and settings["locations"] == expected_locations,
        "local_project_settings_mismatch",
    )
    research = read(transport, path + "/local-research")
    require(
        research.get("configured") is True
        and research.get("research") == []
        and case["project_research"] == [],
        "local_case_requires_empty_research",
    )
    before = read(transport, path + "/tracker-items")
    require(isinstance(before, list), "tracker_response_invalid")
    response = transport.request(
        "POST",
        path + "/questions",
        body={"question": case["question"], "jurisdiction_code": case["jurisdiction"]},
    )
    require(response.status == 200, "local_question_unavailable")
    answer = response.json()
    after = read(transport, path + "/tracker-items")
    require(
        settings == read(transport, path + "/settings")
        and research == read(transport, path + "/local-research"),
        "local_context_changed",
    )
    require(digest(encode(before)) == digest(encode(after)), "local_question_mutated_tracker")
    # Exact deterministic application refusal, not a keyword score over generated advice.
    require(
        normalized(answer["text"]) == normalized(GAP_TEXT) and answer["citations"] == [],
        "explicit_application_gap_missing",
    )
    return {
        "status": "structural_verified",
        "provider": "deployed_application_local_gap",
        "answer": answer["text"],
        "citations": [],
        "tracker_sha256": digest(encode(before)),
        "settings_version": settings["version"],
        "semantic_assessment": "unverified",
        "legal_clearance": False,
    }


def save(path: Path, state: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        output.write(encode(state))
        output.flush()
        os.fsync(output.fileno())
        name = output.name
    os.replace(name, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class Evaluation:
    def __init__(
        self, directory: Path, cases: list[dict[str, Any]], binding: dict[str, Any]
    ) -> None:
        self.directory, self.cases = directory, cases
        self.path = directory / "evaluation.json"
        if self.path.exists():
            self.state: dict[str, Any] = json.loads(self.path.read_bytes())
            require(self.state["binding"] == binding, "evaluation_binding_changed")
        else:
            self.state = {
                "binding": binding,
                "results": {
                    case["id"]: {"status": "unverified", "semantic_assessment": "unverified"}
                    for case in cases
                },
            }
            save(self.path, self.state)

    def execute(
        self,
        case_id: str,
        corpus: Corpus,
        grounder: Grounder | None,
        local_bindings: dict[str, Any],
        transport: Transport,
    ) -> dict[str, Any]:
        case = next(case for case in self.cases if case["id"] == case_id)
        prior = self.state["results"][case_id]
        if prior["status"] != "unverified":
            return self.summary()
        # Durable intent covers provider billing and the HTTP question's unknown outcome.
        self.state["results"][case_id] = {
            "status": "call_outcome_unknown",
            "started_at": datetime.now(UTC).isoformat(),
            "semantic_assessment": "unverified",
        }
        save(self.path, self.state)
        try:
            if case["kind"] == "national-grounding":
                require(grounder is not None, "national_grounder_required")
                assert grounder is not None
                answer = grounder.ground(case["question"], jurisdiction_for(case["jurisdiction"]))
                result = corpus.check(case, answer)
            else:
                result = local_case(case, local_bindings[case_id], transport)
        except ValueError:
            result = {
                "status": "structural_failed",
                "reason": "evidence_validation_failed",
                "semantic_assessment": "unverified",
            }
        except Exception:
            # No logging of SDK exception bodies, project responses, or credentials.
            return self.summary()
        self.state["results"][case_id] = {**result, "completed_at": datetime.now(UTC).isoformat()}
        save(self.path, self.state)
        return self.summary()

    def summary(self) -> dict[str, Any]:
        statuses = {key: value["status"] for key, value in self.state["results"].items()}
        return {
            "cases": statuses,
            "structural_verified": sum(
                value == "structural_verified" for value in statuses.values()
            ),
            "total_cases": len(self.cases),
            "semantic_assessment": "unverified",
            "release_ready": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "legal-evaluation-cases-2026-09-06.json"
    )
    parser.add_argument("--sources", type=Path, default=ROOT / "legal-sources-2026-09-06.json")
    parser.add_argument("--ingestion-directory", type=Path)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--local-bindings", type=Path)
    parser.add_argument("--target", help="Deployed HTTPS origin")
    parser.add_argument("--case", dest="case_id")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    cases_value = json.loads(args.cases.read_bytes())
    cases = cases_from(cases_value)
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "plan_only",
                    "total_cases": len(cases),
                    "cases": [
                        {
                            "id": case["id"],
                            "kind": case["kind"],
                            "jurisdiction": case["jurisdiction"],
                            "status": "unverified",
                        }
                        for case in cases
                    ],
                    "release_ready": False,
                },
                indent=2,
            )
        )
        return
    if not all((args.directory, args.ingestion_directory, args.target, args.case_id)):
        parser.error("execution requires directory, ingestion-directory, target and case")
    require(args.case_id in {case["id"] for case in cases}, "unknown_case")
    # Validate the origin before constructing a transport with credentials.
    from urllib.parse import urlsplit

    origin = urlsplit(args.target)
    require(
        origin.scheme == "https"
        and bool(origin.hostname)
        and not origin.username
        and not origin.password
        and origin.path in {"", "/"}
        and not origin.query
        and not origin.fragment,
        "https_origin_required",
    )
    providers = ProviderConfig.read(
        os.environ, os.environ["GEMINI_MODEL"], os.environ["GEMINI_MODEL_LITE"]
    )
    data_store = os.environ["VERTEX_SEARCH_DATA_STORE_ID"]
    corpus = Corpus(json.loads(args.sources.read_bytes()), args.ingestion_directory, data_store)
    selected = next(case for case in cases if case["id"] == args.case_id)
    local_bindings = json.loads(args.local_bindings.read_bytes()) if args.local_bindings else {}
    transport = HttpTransport(args.target.rstrip("/"), "")
    local_identity = None
    if selected["kind"] == "unsupported-local":
        require(
            set(local_bindings)
            == {case["id"] for case in cases if case["kind"] == "unsupported-local"},
            "local_bindings_missing",
        )
        token = os.environ["CLEARCUT_ACCEPTANCE_ID_TOKEN"]
        transport = HttpTransport(args.target.rstrip("/"), token)
        require(
            read(transport, "/api/health", False)["mode"] == "live", "live_application_required"
        )
        require(
            bool(read(transport, "/api/client-config", False)["projectId"]),
            "firebase_setup_required",
        )
        actor = read(transport, "/api/me")["user_id"]
        local_identity = {
            "actor_sha256": digest(actor.encode()),
            "local_bindings_sha256": digest(encode(local_bindings)),
        }
    binding = {
        "schema": 1,
        "target": args.target.rstrip("/"),
        "data_store": data_store,
        "google_project": os.environ["GOOGLE_CLOUD_PROJECT"],
        "providers": providers.frozen(),
        "cases_sha256": digest(encode(cases_value)),
        "sources_receipt_sha256": corpus.receipt_hash,
    }
    args.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (args.directory / "evaluation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        evaluation = Evaluation(args.directory, cases, binding)
        if local_identity is not None:
            prior = evaluation.state.get("local_identity")
            require(prior is None or prior == local_identity, "local_identity_changed")
            evaluation.state["local_identity"] = local_identity
            save(evaluation.path, evaluation.state)
        if evaluation.state["results"][args.case_id]["status"] != "unverified":
            result = evaluation.summary()
        elif selected["kind"] == "unsupported-local":
            result = evaluation.execute(args.case_id, corpus, None, local_bindings, transport)
        else:
            # Production timeout is milliseconds; keep the client alive until the call completes.
            from google import genai

            from clearcut.adapters.gcp.vertex_search import VertexSearchGrounding

            client = genai.Client(
                vertexai=True,
                project=binding["google_project"],
                location="global",
                http_options=genai.types.HttpOptions(
                    timeout=int(providers.genai_timeout * 1000),
                    retry_options=genai.types.HttpRetryOptions(attempts=1),
                ),
            )
            try:
                grounder = VertexSearchGrounding(
                    client.models, data_store, model=providers.grounding_model
                )
                result = evaluation.execute(args.case_id, corpus, grounder, {}, transport)
            finally:
                client.close()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["cases"][args.case_id] == "structural_verified" else 3)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError):
        print(
            json.dumps(
                {
                    "status": "missing_setup",
                    "semantic_assessment": "unverified",
                    "release_ready": False,
                }
            )
        )
        raise SystemExit(2) from None
