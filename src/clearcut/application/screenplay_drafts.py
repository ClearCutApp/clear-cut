"""Save content before atomically publishing its expected-version pointer.

A rejected concurrent save may leave an unreferenced immutable blob; it never
changes the winning draft or overwrites either writer's original content.
"""

import json
from typing import Any

from clearcut.application.draft_ports import DraftStore, ScreenplayContent
from clearcut.domain.screenplay import Draft, InvalidScreenplay, encode_document


def save_draft(
    store: DraftStore,
    content: ScreenplayContent,
    organization_id: str,
    project_id: str,
    content_id: str,
    expected_version: int,
    document: dict[str, Any],
    actor: str,
    at: str,
) -> Draft:
    if type(expected_version) is not int or expected_version < 0:
        raise InvalidScreenplay("expected_version must be a nonnegative integer")
    encoded = encode_document(document)
    reference = content.put(organization_id, project_id, content_id, encoded)
    return store.save(project_id, expected_version, reference, actor, at)


def read_document(content: ScreenplayContent, draft: Draft) -> dict[str, Any] | None:
    if draft.content is None:
        return None
    value = json.loads(content.get(draft.content))
    if not isinstance(value, dict):
        raise InvalidScreenplay("stored document is invalid")
    encode_document(value)
    return value
