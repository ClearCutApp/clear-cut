"""Cloud Run launch acknowledgement never waits for worker completion."""

from types import SimpleNamespace
from typing import Any

from clearcut.adapters.gcp.job_launcher import CloudRunAnalysisLauncher


def test_launch_uses_server_owned_job_and_only_opaque_analysis_id_without_waiting():
    calls: list[dict[str, Any]] = []

    class Client:
        def run_job(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            return SimpleNamespace(operation=SimpleNamespace(name="operations/accepted"))

    launcher = CloudRunAnalysisLauncher(
        Client(), "projects/project/locations/us-central1/jobs/worker"
    )
    assert launcher.launch("opaque-id") == "operations/accepted"
    assert calls == [
        {
            "request": {
                "name": "projects/project/locations/us-central1/jobs/worker",
                "overrides": {
                    "container_overrides": [
                        {"args": ["-m", "clearcut.worker", "--analysis-id", "opaque-id"]}
                    ]
                },
            },
            "retry": None,
            "timeout": 30,
        }
    ]
