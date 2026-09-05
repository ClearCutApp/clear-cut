# ADR 0012: The API is partitioned by domain, and the cut endpoints come back

Status: Accepted
Date: 2026-09-05

Amends ADR 0011. That record stands unedited; this one supersedes its cut.

## Context

ADR 0011 cut three endpoints to fit four days: `POST /api/projects`,
`POST /api/projects/{id}/bible` and `GET /api/scripts/{script_id}`. The cut was
correct for a submission judged on one analyze call against real services. It is
wrong for a product, and the goal changed on 2026-09-05: ClearCut is now built
as a web application a producer uses, not a demo a judge runs once.

Every cut endpoint is now load-bearing. Without `POST /api/projects` a producer
cannot create the thing every other path hangs off, and `project_id` stays an
arbitrary string that two people can collide on by typing the same word. Without
bible writes, CONTINUITY findings only ever fire for the one project an operator
seeded by hand. Without a script read, Script Review is empty after a page
reload, because findings live only in the response body of the run that produced
them.

The transport has a second problem the cut did not cause. `routes.py` is one
339-line module holding five routes across five unrelated subjects, and
`docs.py` serves a hand-written OpenAPI document with **zero** `tags` and no
`operationId` values. Swagger renders it as a single undifferentiated list. An
API with no domains in its document has no domains.

## Decision

Partition the HTTP adapter and its OpenAPI document into six bounded contexts,
and reinstate all three cut endpoints.

The six are `System`, `Projects`, `Scripts`, `Tracker`, `Bible` and `Questions`.
Each becomes one module under `src/clearcut/adapters/http/`, exporting
`create_<domain>_blueprint`, `TAG`, `PATHS` and `SCHEMAS`. An `openapi.py`
holds the `DOMAINS` tuple and merges them, raising on a duplicate schema name or
a duplicate `(path, method)` pair rather than letting one silently win.

`docs/api/openapi.yaml` is checked in and is the contract. A two-directional
drift test asserts the served document and the checked-in one describe the same
set of operations, in both directions, so neither can move without the other.

**Flask stays.** FastAPI would generate the tagged document from type hints and
serve the SPA through `app.frontend()`, and it would cost a rewrite of the
transport layer, 39 route tests and every adapter's error translation, on a
system whose seven gates are green. The partition above buys the same document
structure for the cost of moving functions between files. The generation is
mechanical either way; what matters is that the domains exist, and a framework
does not grant them.

`POST /api/tracker-items/{id}/actions` is deleted rather than extended. An
action verb that dispatches on a body field is a remote procedure call wearing a
resource's clothes, and two of its four values (`generate_document`,
`stakeholder_link`) raise `ValueError` and return 500 today. It becomes
`POST .../email-drafts` and `POST .../notifications`. The two unimplemented
values get no route at all: a 404 from routing says "this does not exist" more
honestly than a 500 from a handler that knows it does not exist.

Every path nests under the project that owns it. The top-level
`PATCH /api/tracker-items/{id}` goes away, so item ids stop being globally
addressable strings whose project is inferred from a database row.

## Consequences

Swagger renders six collapsible groups, and a reader can find the four tracker
operations without reading past the bible. That is the visible half.

The invisible half is that the six modules give the four parallel workers
disjoint files. Without the partition every route change queues behind every
other route change in one 339-line file.

Reinstating the endpoints costs three use cases, three stores and a migration.
The migration is destructive -- see ADR 0014 -- and needs a human to approve it.

The drift test is a maintenance cost with teeth. Adding a route without
documenting it fails the build, which is the point, and it will be annoying at
least once.

Flask staying means the OpenAPI document is hand-maintained rather than derived
from the handlers. The drift test is what makes that safe, and it is a weaker
guarantee than a type-driven generator. If the document ever grows past what two
people can hold in their heads, revisit this.
