"""Bounded, resumable acceptance of an authenticated deployed synthetic project.

Default is read-only preflight. --advance authorizes synthetic resource creation and
provider work. A mutation without a validated response is never automatically retried.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

import httpx
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from clearcut.domain.screenplay import encode_document

MAX_RESPONSE = 16 * 1024 * 1024
STEPS = (
    "organization",
    "project",
    "import",
    "edit",
    "stale_edit",
    "draft_readback",
    "revision",
    "revision_readback",
    "enqueue",
    "poll",
    "committed",
    "tracker",
    "evidence",
    "evidence_readback",
    "details",
    "clear",
    "reconfirm",
    "clearance_readback",
    "report_context",
    "report",
    "pdf",
    "csv",
)
REQUIRED_PATHS = {
    "/api/me",
    "/api/organizations",
    "/api/projects",
    "/api/projects/{project_id}/imports",
    "/api/projects/{project_id}/draft",
    "/api/projects/{project_id}/revisions",
    "/api/projects/{project_id}/scripts",
    "/api/projects/{project_id}/analyses/{analysis_id}",
    "/api/projects/{project_id}/reports/context",
    "/api/projects/{project_id}/reports",
    "/api/projects/{project_id}/tracker-items/{item_id}/reconfirmation",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def identifier(value: Any) -> str:
    require(
        isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value)),
        "invalid_resource_identity",
    )
    return str(value)


def synthetic_pdf(run_id: str) -> bytes:
    output = BytesIO()
    canvas = Canvas(output, invariant=1)
    canvas.drawString(72, 750, "INT. RECORD STORE - NIGHT")
    canvas.drawString(72, 720, "A Coca-Cola bottle sits beside a radio playing Hotel California.")
    canvas.drawString(72, 690, f"Synthetic acceptance fixture only: {run_id}")
    canvas.save()
    return output.getvalue()


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str = "application/json"

    def json(self) -> Any:
        require("application/json" in self.content_type, "json_response_required")
        return json.loads(self.body)


class Transport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        body: dict[str, Any] | None = None,
        file: bytes | None = None,
    ) -> Response: ...


class HttpTransport:
    def __init__(self, target: str, token: str) -> None:
        self.target, self.token = target, token

    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        body: dict[str, Any] | None = None,
        file: bytes | None = None,
    ) -> Response:
        require(path.startswith("/api/") and not path.startswith("//"), "invalid_request_path")
        headers = {"Authorization": f"Bearer {self.token}"} if authenticated else {}
        kwargs: dict[str, Any] = {"headers": headers}
        if file is None:
            kwargs["json"] = body
        else:
            kwargs["files"] = {"file": ("synthetic-acceptance.pdf", file, "application/pdf")}
            kwargs["data"] = body or {}
        # No retries, redirect following, ambient proxy credentials or response-body logging.
        with httpx.Client(
            timeout=httpx.Timeout(45, connect=10), follow_redirects=False, trust_env=False
        ) as client:
            with client.stream(method, self.target + path, **kwargs) as response:
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    require(len(chunks) + len(chunk) <= MAX_RESPONSE, "response_too_large")
                    chunks.extend(chunk)
                return Response(
                    response.status_code, bytes(chunks), response.headers.get("content-type", "")
                )


class Acceptance:
    """Single writer; caller holds the receipt lock across preflight and advancement."""

    def __init__(self, target: str, run_id: str, directory: Path, transport: Transport) -> None:
        parsed = urlsplit(target)
        require(
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment,
            "https_origin_required",
        )
        self.target, self.run_id = target.rstrip("/"), identifier(run_id)
        self.directory, self.transport = directory, transport
        self.fixture = synthetic_pdf(run_id)
        self.path = directory / "receipt.json"
        self.state: dict[str, Any] = {}

    def save(self) -> None:
        self.state["updated_at"] = datetime.now(UTC).isoformat()
        with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as handle:
            handle.write(canonical(self.state))
            handle.flush()
            os.fsync(handle.fileno())
            name = handle.name
        os.replace(name, self.path)
        fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def get(self, path: str, authenticated: bool = True) -> Any:
        response = self.transport.request("GET", path, authenticated=authenticated)
        require(response.status == 200, "read_denied_or_unavailable")
        return response.json()

    def preflight(self) -> None:
        require(self.get("/api/health", False).get("mode") == "live", "live_mode_required")
        config = self.get("/api/client-config", False)
        require(
            all(
                isinstance(config.get(key), str) and config[key]
                for key in ("apiKey", "authDomain", "projectId", "appId")
            ),
            "firebase_client_setup_required",
        )
        spec = self.get("/api/openapi.json", False)
        require(REQUIRED_PATHS <= set(spec.get("paths", {})), "deployed_contract_is_obsolete")
        responses = spec["paths"]["/api/projects/{project_id}/scripts"]["post"]["responses"]
        require("202" in responses, "async_analysis_contract_required")
        denied = self.transport.request("GET", "/api/projects", authenticated=False)
        require(denied.status == 401, "anonymous_project_access_not_denied")
        actor = self.get("/api/me").get("user_id")
        require(isinstance(actor, str) and bool(actor), "verified_actor_required")
        binding = {
            "schema": 1,
            "target": self.target,
            "run_id": self.run_id,
            "actor_sha256": digest(actor.encode()),
            "input_sha256": digest(self.fixture),
            "contract_sha256": digest(canonical(spec)),
            "firebase_project": config["projectId"],
        }
        if self.path.exists():
            self.state = json.loads(self.path.read_bytes())
            require(self.state.get("binding") == binding, "receipt_binding_changed")
            require(self.state.get("cursor") in range(len(STEPS) + 1), "invalid_receipt_cursor")
        else:
            self.state = {
                "binding": binding,
                "cursor": 0,
                "status": "ready",
                "resources": {},
                "evidence": {},
                "operations": [],
            }
            self.save()

    def advance(self, maximum_steps: int = 8) -> dict[str, Any]:
        require(1 <= maximum_steps <= 32, "step_budget_out_of_range")
        self.preflight()
        if self.state["status"] in {"unknown", "failed", "success"}:
            return self.summary()
        # A crash after persisting intent is indistinguishable from a lost acknowledgement.
        if self.state.get("intent"):
            self.state.update(status="unknown", reason="unacknowledged_mutation")
            self.save()
            return self.summary()
        for _ in range(maximum_steps):
            step = STEPS[self.state["cursor"]]
            try:
                if not self.step(step):
                    self.state.update(status="pending", reason="analysis_still_running")
                    self.save()
                    return self.summary()
            except (httpx.HTTPError, TimeoutError, OSError):
                uncertain = bool(self.state.get("intent"))
                self.state.update(
                    status="unknown" if uncertain else "pending",
                    reason="mutation_outcome_unknown"
                    if uncertain
                    else "read_temporarily_unavailable",
                )
                self.save()
                return self.summary()
            except Exception:
                uncertain = bool(self.state.get("intent"))
                self.state.update(
                    status="unknown" if uncertain else "failed",
                    reason="mutation_outcome_unknown" if uncertain else "acceptance_check_failed",
                )
                self.save()
                return self.summary()
            self.state.pop("intent", None)
            self.state["cursor"] += 1
            self.state.update(
                status="success" if self.state["cursor"] == len(STEPS) else "pending",
                reason="complete" if self.state["cursor"] == len(STEPS) else "step_budget",
            )
            self.save()
            if self.state["status"] == "success":
                break
        return self.summary()

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.state["status"],
            "reason": self.state.get("reason", "preflight"),
            "completed_steps": self.state["cursor"],
            "total_steps": len(STEPS),
            "next_step": STEPS[self.state["cursor"]] if self.state["cursor"] < len(STEPS) else None,
            "release_ready": False,
        }

    def mutate(
        self,
        step: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        file: bytes | None = None,
        expected: int = 200,
    ) -> Any:
        intent = {
            "step": step,
            "method": method,
            "path": path,
            "request_sha256": digest(canonical(body)),
            "file_sha256": digest(file) if file else None,
        }
        self.state["intent"] = intent
        self.save()
        response = self.transport.request(method, path, body=body, file=file)
        self.state["operations"].append({**intent, "http_status": response.status})
        # Even an error may follow an accepted upload. Preserve intent for reconciliation.
        require(response.status == expected, "mutation_status_mismatch")
        return response.json()

    def step(self, step: str) -> bool:
        resources, evidence = self.state["resources"], self.state["evidence"]
        project = "/api/projects/" + quote(resources.get("project_id", ""), safe="")
        item = project + "/tracker-items/" + quote(resources.get("item_id", ""), safe="")
        if step == "organization":
            result = self.mutate(
                step,
                "POST",
                "/api/organizations",
                {"name": "Acceptance " + self.run_id},
                expected=201,
            )
            resources["organization_id"] = identifier(result["organization_id"])
        elif step == "project":
            result = self.mutate(
                step,
                "POST",
                "/api/projects",
                {
                    "title": "Synthetic acceptance " + self.run_id,
                    "organization_id": resources["organization_id"],
                    "jurisdiction_code": "AR",
                },
                expected=201,
            )
            resources["project_id"] = identifier(result["project_id"])
        elif step == "import":
            result = self.mutate(
                step, "POST", project + "/imports", {"expected_version": "0"}, self.fixture, 201
            )
            draft = result["draft"]
            require(
                draft["project_id"] == resources["project_id"] and draft["version"] == 1,
                "import_draft_binding_mismatch",
            )
            require("Coca-Cola" in json.dumps(draft["document"]), "pdf_text_not_imported")
            resources["original_file_id"] = identifier(result["original"]["file_id"])
            evidence["import_document_sha256"] = digest(canonical(draft["document"]))
        elif step == "edit":
            draft = self.get(project + "/draft")
            require(
                draft["version"] == 1
                and digest(canonical(draft["document"])) == evidence["import_document_sha256"],
                "import_changed_before_edit",
            )
            document = deepcopy(draft["document"])
            last = document["content"][-1]
            document["content"].append(
                {
                    "type": "paragraph",
                    "attrs": {
                        "blockId": "acceptance-edit-" + self.run_id,
                        "sceneId": last["attrs"]["sceneId"],
                        "kind": "action",
                    },
                    "content": [{"type": "text", "text": "The radio falls silent."}],
                }
            )
            result = self.mutate(
                step, "PUT", project + "/draft", {"expected_version": 1, "document": document}
            )
            require(
                result["version"] == 2 and result["document"] == document, "edited_draft_mismatch"
            )
            evidence["edited_document_sha256"] = digest(canonical(document))
            evidence["edited_storage_sha256"] = digest(encode_document(document))
        elif step == "stale_edit":
            draft = self.get(project + "/draft")
            self.mutate(
                step,
                "PUT",
                project + "/draft",
                {"expected_version": 1, "document": draft["document"]},
                expected=409,
            )
        elif step == "draft_readback":
            draft = self.get(project + "/draft")
            require(
                draft["version"] == 2
                and digest(canonical(draft["document"])) == evidence["edited_document_sha256"],
                "stale_write_changed_draft",
            )
        elif step == "revision":
            result = self.mutate(
                step, "POST", project + "/revisions", {"expected_version": 2}, expected=201
            )
            require(result["draft_version"] == 2, "revision_version_mismatch")
            resources["revision_id"] = identifier(result["revision_id"])
            evidence["revision_sha256"] = result["sha256"]
        elif step == "revision_readback":
            revision = self.get(project + "/revisions/" + resources["revision_id"])
            require(
                revision["draft_version"] == 2
                and revision["revision_id"] == resources["revision_id"]
                and revision["sha256"] == evidence["revision_sha256"]
                and evidence["edited_storage_sha256"] == revision["sha256"]
                and digest(canonical(revision["document"])) == evidence["edited_document_sha256"],
                "revision_content_mismatch",
            )
        elif step == "enqueue":
            result = self.mutate(
                step,
                "POST",
                project + "/scripts",
                {"revision_id": resources["revision_id"], "jurisdiction_code": "AR"},
                expected=202,
            )
            require(result["revision_id"] == resources["revision_id"], "job_revision_mismatch")
            resources["analysis_id"] = identifier(result["analysis_id"])
            resources["script_id"] = identifier(result["script_id"])
        elif step == "poll":
            result = self.get(project + "/analyses/" + resources["analysis_id"])
            require(
                all(
                    result[key] == resources[key]
                    for key in ("analysis_id", "project_id", "script_id", "revision_id")
                ),
                "job_identity_mismatch",
            )
            require(result["state"] in {"QUEUED", "RUNNING", "SUCCEEDED"}, "analysis_failed")
            evidence["job_state"] = result["state"]
            return bool(result["state"] == "SUCCEEDED")
        elif step == "committed":
            result = self.get(project + "/scripts/" + resources["script_id"])
            require(
                result["revision_id"] == resources["revision_id"]
                and result["revision_draft_version"] == 2
                and bool(result["findings"]),
                "committed_analysis_mismatch",
            )
            require(bool(result["scene_anchors"]), "committed_scene_anchors_missing")
            evidence["committed_sha256"] = digest(canonical(result))
            evidence["bound_items"] = sorted(
                key
                for key, binding in result["clearance_bindings"].items()
                if binding.get("present") is True
                and binding.get("revision_id") == resources["revision_id"]
            )
        elif step == "tracker":
            rows = self.get(project + "/tracker-items")
            require(isinstance(rows, list) and bool(rows), "no_clearance_findings")
            selected = next(row for row in rows if row["item_id"] in evidence["bound_items"])
            require(selected["state"] == "BLOCKED", "initial_clearance_not_blocked")
            resources["item_id"] = identifier(selected["item_id"])
            evidence["item_version"] = selected["version"]
        elif step == "evidence":
            result = self.mutate(
                step, "POST", project + "/documents", file=self.fixture, expected=201
            )
            require(result["sha256"] == digest(self.fixture), "evidence_hash_mismatch")
            resources["evidence_file_id"] = identifier(result["file_id"])
        elif step == "evidence_readback":
            result = self.transport.request(
                "GET", project + "/documents/" + resources["evidence_file_id"]
            )
            require(
                result.status == 200 and result.body == self.fixture, "evidence_download_mismatch"
            )
        elif step == "details":
            result = self.mutate(
                step,
                "PUT",
                item + "/details",
                {
                    "expected_version": evidence["item_version"],
                    "note": "Synthetic acceptance only; not a real rights authorization.",
                    "clearance_conditions": "Synthetic fixture only.",
                    "due_date": "",
                    "assignee_id": "",
                    "evidence_file_ids": [resources["evidence_file_id"]],
                    "draft_email": None,
                },
            )
            require(
                result["evidence_file_ids"] == [resources["evidence_file_id"]],
                "evidence_link_missing",
            )
            evidence["item_version"] = result["version"]
        elif step == "clear":
            result = self.mutate(
                step,
                "PATCH",
                item,
                {"expected_version": evidence["item_version"], "state": "CLEARED"},
            )
            require(result["state"] == "CLEARED", "clearance_transition_failed")
            evidence["item_version"] = result["version"]
        elif step == "reconfirm":
            result = self.mutate(
                step,
                "POST",
                item + "/reconfirmation",
                {
                    "expected_version": evidence["item_version"],
                    "revision_id": resources["revision_id"],
                    "acknowledged": True,
                },
            )
            evidence["item_version"] = result["version"]
        elif step == "clearance_readback":
            result = self.get(item)
            require(
                result["state"] == "CLEARED"
                and not result["needs_review"]
                and result["version"] == evidence["item_version"]
                and result["evidence_file_ids"] == [resources["evidence_file_id"]],
                "clearance_readback_mismatch",
            )
        elif step == "report_context":
            context = self.get(project + "/reports/context")
            snapshot = context["snapshot"]
            require(
                context["configured"]
                and all(snapshot[key] == resources[key] for key in ("analysis_id", "revision_id")),
                "report_snapshot_mismatch",
            )
            require(snapshot["counts"]["confirmed_cleared"] == 1, "clearance_count_mismatch")
            evidence["report_selection"] = {
                key: snapshot[key]
                for key in ("analysis_id", "revision_id", "expected_generation", "expected_epoch")
            }
        elif step == "report":
            result = self.mutate(
                step,
                "POST",
                project + "/reports",
                {**evidence["report_selection"], "language": "en"},
                expected=201,
            )
            require(
                result["revision_id"] == resources["revision_id"]
                and result["analysis_id"] == resources["analysis_id"]
                and result["generation_id"] == evidence["report_selection"]["expected_generation"]
                and result["clearance_epoch"] == evidence["report_selection"]["expected_epoch"]
                and result["counts"]["confirmed_cleared"] == 1,
                "saved_report_mismatch",
            )
            resources["report_id"] = identifier(result["report_id"])
            evidence["report_counts"] = result["counts"]
        elif step in {"pdf", "csv"}:
            result = self.transport.request(
                "GET", project + "/reports/" + resources["report_id"] + "/download?format=" + step
            )
            require(result.status == 200, "report_download_failed")
            if step == "pdf":
                require(result.body.startswith(b"%PDF-"), "report_pdf_invalid")
                text = "\n".join(
                    page.extract_text() for page in PdfReader(BytesIO(result.body)).pages
                )
                require(
                    all(resources[key] in text for key in ("item_id", "report_id", "revision_id")),
                    "report_pdf_identity_missing",
                )
            else:
                rows = list(csv.DictReader(StringIO(result.body.decode("utf-8-sig"))))
                require(
                    len(rows) == evidence["report_counts"]["total_retained"]
                    and any(
                        row["item_id"] == resources["item_id"]
                        and resources["evidence_file_id"] in row["evidence_ids"]
                        and row["state"] == "CLEARED"
                        for row in rows
                    ),
                    "report_csv_mismatch",
                )
                require(
                    all(
                        row["report_id"] == resources["report_id"]
                        and row["report_revision"] == resources["revision_id"]
                        for row in rows
                    ),
                    "report_csv_identity_mismatch",
                )
            evidence[step + "_sha256"] = digest(result.body)
            evidence[step + "_bytes"] = len(result.body)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--advance", action="store_true")
    parser.add_argument("--steps", type=int, default=8)
    args = parser.parse_args()
    token = os.environ.get("CLEARCUT_ACCEPTANCE_ID_TOKEN", "").strip()
    if not token:
        print(json.dumps({"status": "missing_setup", "reason": "firebase_id_token_required"}))
        raise SystemExit(2)
    args.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (args.directory / "receipt.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run = Acceptance(
                args.target,
                args.run_id,
                args.directory,
                HttpTransport(args.target.rstrip("/"), token),
            )
            if args.advance:
                result = run.advance(args.steps)
            else:
                run.preflight()
                result = run.summary()
        except Exception:
            result = {
                "status": "missing_setup",
                "reason": "preflight_or_receipt_unavailable",
                "release_ready": False,
            }
    print(json.dumps(result))
    raise SystemExit(
        {"success": 0, "ready": 0, "pending": 3, "unknown": 4, "failed": 5, "missing_setup": 2}[
            result["status"]
        ]
    )


if __name__ == "__main__":
    main()
