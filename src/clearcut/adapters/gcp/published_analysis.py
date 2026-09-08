"""Read committed immutable manifests; ClickHouse projection timing is irrelevant."""

from typing import Any

from clearcut.application.analysis_documents import read_finding, read_script
from clearcut.application.durable_ports import AnalysisArtifacts
from clearcut.domain.errors import RecordNotFound
from clearcut.domain.finding import Finding
from clearcut.domain.screenplay import ContentReference
from clearcut.domain.script import Script


class PublishedAnalysis:
    def __init__(self, client: Any, artifacts: AnalysisArtifacts) -> None:
        self.client, self.artifacts = client, artifacts

    def _scripts(self, project_id: str) -> Any:
        return (
            self.client.collection("project_access")
            .document(project_id)
            .collection("analyzed_scripts")
        )

    def manifest(self, project_id: str, script_id: str) -> dict[str, Any]:
        data = self._scripts(project_id).document(script_id).get().to_dict()
        if not data:
            raise RecordNotFound("analyzed script not found")
        manifest = self.artifacts.get(ContentReference(**data["manifest"]))
        if (
            manifest.get("project_id") != project_id
            or manifest.get("script", {}).get("script_id") != script_id
        ):
            raise RecordNotFound("analyzed script not found")
        return manifest

    def get(self, project_id: str, script_id: str) -> Script:
        return read_script(self.manifest(project_id, script_id)["script"])

    def for_project(self, project_id: str) -> list[Script]:
        return [
            self.get(project_id, row.to_dict()["script_id"])
            for row in self._scripts(project_id).order_by("version").stream()
        ]

    def latest(self, project_id: str) -> Script | None:
        rows = list(
            self._scripts(project_id).order_by("version", direction="DESCENDING").limit(1).stream()
        )
        return self.get(project_id, rows[0].to_dict()["script_id"]) if rows else None

    def save(self, script: Script) -> None:
        raise RuntimeError("scripts are published only with complete analysis generations")


class PublishedFindings:
    def __init__(self, published: PublishedAnalysis) -> None:
        self.published = published

    def for_script(self, project_id: str, script_id: str) -> list[Finding]:
        manifest = self.published.manifest(project_id, script_id)
        bindings = manifest.get("clearance_bindings", {})
        return [
            read_finding(value)
            for value in manifest["findings"]
            if bindings.get(value["finding_id"], {}).get("present", True)
        ]

    def save(self, project_id: str, script_id: str, findings: list[Finding]) -> None:
        raise RuntimeError("findings are published only with complete analysis generations")
