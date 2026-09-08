#!/usr/bin/env python3
"""Print additive scene projection DDL; --apply explicitly creates the table."""

import argparse
import re
from typing import Any


def statement(project: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9-]+", project):
        raise ValueError("project must be a plain cloud project identifier")
    return f"""CREATE TABLE IF NOT EXISTS `{project}.clearcut.analysis_scene_vectors` (
      doc_id STRING, content STRING, embedding ARRAY<FLOAT64>, project_id STRING,
      organization_id STRING, analysis_id STRING, revision_id STRING, scene_id STRING,
      kind STRING, episode STRING, scene_number INT64, page INT64, content_hash STRING,
      fact_id STRING, fact_kind STRING, source STRING
    ) CLUSTER BY organization_id, project_id, analysis_id"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    sql = statement(args.project)
    print(sql)
    if args.apply:
        from google.cloud import bigquery

        client: Any = bigquery.Client(project=args.project, location="us-central1")
        client.query(sql, timeout=30, retry=None, job_retry=None).result(
            timeout=30, retry=None, job_retry=None
        )


if __name__ == "__main__":
    main()
