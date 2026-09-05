"""Reads one project's bible (`getProjectBible`,
`GET /api/projects/{project_id}/bible`).

`LoreStore.facts` is the read this uses rather than `search`: the producer
asked for the whole bible, and a similarity search would rank and truncate a
list they expect entire (`application/ports.py`).

A project with nothing recorded answers with an empty `facts` tuple, matching
the wire contract's "an empty `facts` array when nothing has been recorded".
`ProjectBible.__post_init__` rejects a repeated `fact_id`, and that rejection
travels: a bible that silently dropped a duplicate would hide a corrupt index
from the producer reading it.
"""

from clearcut.application.ports import LoreStore
from clearcut.domain.bible import ProjectBible


class GetBible:
    """`GetBible(lore)`."""

    def __init__(self, lore: LoreStore) -> None:
        self._lore = lore

    def execute(self, project_id: str) -> ProjectBible:
        return ProjectBible(project_id=project_id, facts=tuple(self._lore.facts(project_id)))
