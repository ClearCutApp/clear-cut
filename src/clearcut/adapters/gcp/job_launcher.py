"""Cloud Run launches are acknowledged without waiting for worker completion."""

from typing import Any

from clearcut.domain.errors import SourceUnavailable


class CloudRunAnalysisLauncher:
    def __init__(self, client: Any, job_name: str) -> None:
        self.client, self.job_name = client, job_name

    def launch(self, analysis_id: str) -> str:
        try:
            operation = self.client.run_job(
                request={
                    "name": self.job_name,
                    "overrides": {
                        "container_overrides": [
                            {"args": ["-m", "clearcut.worker", "--analysis-id", analysis_id]}
                        ]
                    },
                },
                retry=None,
                timeout=30,
            )
            return str(operation.operation.name)
        except Exception as exc:
            raise SourceUnavailable("analysis worker launch unavailable") from exc
