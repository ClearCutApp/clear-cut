# ClearCut engineering guidance

The approved product contract is [docs/recovery/specification.md](docs/recovery/specification.md).
Track implementation and evidence in [docs/recovery/checklist.md](docs/recovery/checklist.md).
Historical `.claude/CHECKPOINTS.md`, role prompts and planning documents are
reference history. They do not mandate a leader/implementer/reviewer loop.

Preserve user changes. Use one writer and bounded vertical slices. Select direct
implementation unless the user explicitly selects SDD. Do not enable receipt-driven
review or invent approval. Follow the active runtime permissions; unsupported hooks
are never a security boundary. Never expose secret files, credentials or screenplay
contents in telemetry. Technical artifacts default to English.

Dependencies point inward: adapters → application → domain. Domain is pure stdlib;
application declares narrow I/O ports; adapters translate external errors;
`composition.py` wires concrete collaborators. Preserve Flask and React/Vite.

Verify changed behavior with meaningful regression tests. Run ruff, formatting
checks, mypy, backend tests, frontend typecheck/tests and production build as
applicable. `.claude/init.sh check` and `.claude/init.sh live` remain useful commands;
`verify` checks historical orchestration only. Live checks must return real provider
evidence; missing credentials and skipped tests are unverified. Keep API contracts
and frontend callers aligned. No release-ready claim until deployed acceptance passes.

Keep decisions, discoveries and outcomes in Engram when available; memory failure
never blocks the user-facing answer. Conventional commits only, without AI attribution.
