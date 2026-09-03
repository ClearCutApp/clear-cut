# ADR 0002: Pin Gemini 3 model IDs

Status: Accepted
Date: 2026-08-29

## Context

The legacy docs pin gemini-1.5-pro in four files, six occurrences in total.
That model is retired. gemini-2.5-pro returns a 404 reading "no longer
available to new users" on newly created GCP projects, and a fresh hackathon
project running on the $100 credits is exactly that kind of project.

## Decision

Extraction and orchestration run on gemini-3.7-flash, which is GA and supports
structured output together with tools. High-volume per-scene calls run on
gemini-3.1-flash-lite. gemini-3.1-pro-preview stays noted as an upgrade path
only if the project gets allowlisted, and it serves from the global endpoint
only. Three API rules differ from habit and bind here. Temperature stays at the
default 1.0, because Gemini 3 output degrades when it is lowered. thinking_level
controls reasoning depth. We pin output shape with response_schema instead of
relying on response_mime_type alone.

## Consequences

This record supersedes the six stale pins in docs/resources/; we do not edit them in
place, so readers of those files must check here first. Model IDs live in
configuration, which makes the next generation swap a one-line change. The
flash tier may reason more weakly than a pro model on hard findings, and the
pro-preview path, if we ever take it, adds a preview-availability risk.

## Amendment, 2026-09-03: the pinned models are global-endpoint only

Probed against the real API on the first live run (CP-055). In `us-central1`,
`gemini-3.7-flash`, `gemini-3.1-flash-lite` and `gemini-3-flash-preview` all
return `404 NOT_FOUND` with "your project does not have access to it". All three
answer on the `global` endpoint. The 2.5 family answers on both.

This ADR already noted the global-only constraint for `gemini-3.1-pro-preview`.
It holds for the whole Gemini 3 generation, including the two models pinned
here, so the note was narrower than the fact.

`composition.py` built every client at `us-central1` and now keeps two
locations: `_GENAI_LOCATION = "global"` for the genai client, and
`_GCP_LOCATION = "us-central1"` for BigQuery and the embeddings, whose dataset
does not exist at global. Collapsing them back into one constant breaks
whichever service loses, and a test asserts they differ.

The decision itself stands. The models are right; the region was wrong.
