"""Lists every stored version of one project's script
(docs/api/openapi.yaml, `GET /api/projects/{project_id}/scripts`).

Two collaborators because the response is two reads: `ScriptStore` holds the
versions, `FindingStore` holds the findings each one raised. Counting them in
the use case rather than storing a count on `Script` keeps the number honest
when a re-analysis writes new findings against a version already saved.

Scenes and findings themselves stay out of this response. A project with
eighty-four scenes across four versions would send the whole screenplay four
times to draw a list, so the contract's `ScriptSummary` carries counts and
`GET /api/projects/{project_id}/scripts/{script_id}` carries the rest.
"""

from dataclasses import dataclass

from clearcut.application.ports import FindingStore, ScriptStore
from clearcut.domain.script import Script


@dataclass(frozen=True)
class ScriptListing:
    """One script version and the number of findings raised against it.

    The scene count the contract also reports is `len(script.scenes)`, which
    the route reads off `script` rather than being handed twice.
    """

    script: Script
    finding_count: int


class ListScripts:
    """`ListScripts(scripts, findings)`."""

    def __init__(self, scripts: ScriptStore, findings: FindingStore) -> None:
        self._scripts = scripts
        self._findings = findings

    def execute(self, project_id: str) -> list[ScriptListing]:
        """Every version of the project's script, newest first.

        Two rows can share a version number: the mock scenario seeds one and
        an analysis at the same number writes another. The most recently
        stored wins the tie, which is what `ScriptStore.latest_script` has
        always meant.

        A project that has never had a script analyzed answers with `[]`
        rather than raising. The contract's 404 on this path is about a
        project that does not exist, and `ScriptStore` cannot tell that apart
        from a project with no versions yet, so the route checks the project
        and owns the distinction.
        """
        stored = self._scripts.for_project(project_id)
        # Ties break on store order, most recently stored first. Sorting on
        # `version` alone leaves them in store order, which is oldest first,
        # so the older of two rows at the same number won the top of the list
        # -- and `latest_script` already means "the last one stored", so the
        # two reads disagreed about which version is current.
        newest_first = sorted(
            enumerate(stored),
            key=lambda pair: (pair[1].version, pair[0]),
            reverse=True,
        )
        return [
            ScriptListing(
                script=script,
                finding_count=len(self._findings.for_script(project_id, script.script_id)),
            )
            for _, script in newest_first
        ]
