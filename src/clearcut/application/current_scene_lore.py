"""Questions disclose index freshness and cite the exact saved revision."""

from urllib.parse import quote

from clearcut.application.lore_projection_ports import LoreProjectionQueue, SceneVectors
from clearcut.application.ports import GroundedAnswer
from clearcut.domain.finding import Citation


class CurrentSceneLore:
    def __init__(self, queue: LoreProjectionQueue, vectors: SceneVectors) -> None:
        self.queue, self.vectors = queue, vectors

    def answer(self, project_id: str, question: str) -> GroundedAnswer:
        scope = self.queue.current(project_id)
        if scope["state"] == "not_analyzed":
            return GroundedAnswer("Save and analyze a screenplay revision to ask about its scenes.")
        if scope["state"] != "ready":
            return GroundedAnswer(
                "Current revision scene evidence is not indexed yet. "
                "No earlier revision's scenes were used for this answer."
            )
        rows = self.vectors.search(scope, question, 3)
        if self.queue.current(project_id).get("analysis_id") != scope["analysis_id"]:
            return GroundedAnswer(
                "A newer analysis was published while retrieving scene evidence. "
                "Ask again for the current revision."
            )
        if not rows:
            return GroundedAnswer("No matching scene evidence was found in the analyzed revision.")
        citations = tuple(
            Citation(
                (
                    f"/projects/{quote(project_id, safe='')}/editor"
                    f"?revision={quote(row['revision_id'], safe='')}"
                    f"&scene={quote(row['scene_id'], safe='')}"
                ),
                f"{row['source']} · scene starts on page {row['page']}",
                row["text"],
            )
            for row in rows
        )
        return GroundedAnswer(
            "Scene evidence from the analyzed revision:\n\n"
            + "\n\n".join(f"{citation.title}\n{citation.snippet}" for citation in citations),
            citations,
        )
