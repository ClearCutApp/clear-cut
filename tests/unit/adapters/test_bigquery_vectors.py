from unittest.mock import Mock

import pytest
from google.api_core.exceptions import Conflict

from clearcut.adapters.bigquery.vectors import BigQueryVectors


def test_queries_bind_project_and_kind_before_ranking_and_limit_with_budget():
    client = Mock()
    client.query.return_value.result.return_value = [
        {
            "doc_id": "id",
            "content": "Private fact",
            "project_id": "project' OR TRUE --",
            "kind": "bible_fact",
            "fact_id": "FACT-1",
            "fact_kind": "LORE",
            "distance": 0.25,
        }
    ]
    store = BigQueryVectors(client, "cloud.clearcut.lore_vectors", timeout=13)
    results = store.similarity_search_by_vector_with_score(
        [0.5, 0.25], {"project_id": "project' OR TRUE --", "kind": "bible_fact"}, 5
    )
    sql = client.query.call_args.args[0]
    assert "OR TRUE" not in sql
    assert sql.index("WHERE `kind`") < sql.index("ML.DISTANCE") < sql.index("LIMIT")
    options = client.query.call_args.kwargs
    assert options["timeout"] == 13 and options["retry"] is None and options["job_retry"] is None
    assert options["job_config"].maximum_bytes_billed == 1_000_000_000
    values = [value.to_api_repr() for value in options["job_config"].query_parameters]
    assert any(value["parameterValue"].get("value") == "project' OR TRUE --" for value in values)
    client.query.return_value.result.assert_called_once_with(timeout=13, retry=None, job_retry=None)
    assert results[0][0].page_content == "Private fact" and results[0][1] == 0.25


def test_empty_scope_and_identifier_injection_never_reach_bigquery():
    client = Mock()
    with pytest.raises(ValueError):
        BigQueryVectors(client, "project.dataset.table`; DROP TABLE other")
    store = BigQueryVectors(client, "project.dataset.table")
    for filters in (None, {}, {"project_id": ""}, {"project_id": "one", "x`": "two"}):
        with pytest.raises(ValueError):
            store.get_documents(filter=filters)
    assert client.mock_calls == []


def test_lost_load_response_replays_same_job_and_resumes_conflict_without_append():
    client = Mock()
    client.load_table_from_json.side_effect = TimeoutError("response unknown")
    store = BigQueryVectors(client, "project.dataset.table", timeout=19)
    metadata: list[dict[str, str | int]] = [
        {"project_id": "one", "kind": "bible_fact", "content_hash": "sha"}
    ]
    with pytest.raises(TimeoutError):
        store.add_texts_with_embeddings(["Private fact"], [[1.0]], metadata)
    original_id = client.load_table_from_json.call_args.kwargs["job_id"]
    conflict = Conflict("already accepted")  # type: ignore[no-untyped-call]
    client.load_table_from_json.side_effect = conflict
    ids = store.add_texts_with_embeddings(["Private fact"], [[1.0]], metadata)
    options = client.load_table_from_json.call_args.kwargs
    assert options["job_id"] == original_id and "Private" not in original_id
    assert options["num_retries"] == 0 and options["timeout"] == 19
    assert options["job_config"].create_disposition == "CREATE_NEVER"
    client.get_job.assert_called_once_with(
        original_id, location="us-central1", timeout=19, retry=None
    )
    client.get_job.return_value.result.assert_called_once_with(timeout=19, retry=None)
    assert len(ids) == 1


def test_invalid_later_vector_cannot_partially_load_a_batch():
    client = Mock()
    store = BigQueryVectors(client, "project.dataset.table")
    with pytest.raises(ValueError):
        store.add_texts_with_embeddings(
            ["first", "second"],
            [[1.0], [float("nan")]],
            [{"project_id": "one"}, {"project_id": "one"}],
        )
    client.load_table_from_json.assert_not_called()
