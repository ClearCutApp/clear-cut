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

## Amendment, 2026-09-05: both pins are on the deprecation table, and one is not injected

Checked against Google's published deprecation list on 2026-09-05.
`gemini-3.7-flash` was deprecated on 2026-08-13 with no shutdown date
announced. `gemini-3.1-flash-lite` was deprecated on 2026-05-07 **with a
shutdown date of 2027-05-07**, and names `gemini-3.5-flash-lite` as its
replacement.

Neither breaks today. Deprecated means no new work goes into it, not that it
stops answering, and the lite model has eight months. Repinning under a product
deadline would swap two known-good models, each with a tuned `response_schema`
and a live test proving what it returns, for two unmeasured ones. That is a
change to make deliberately, with the live tier as the judge, not as a footnote
to unrelated work.

What this amendment does change: the successor is now written down rather than
rediscovered under time pressure. When the lite model is repinned it goes to
`gemini-3.5-flash-lite`, and the extractor's pin is re-evaluated at the same
time so both move once.

Separately, a defect this check surfaced. `adapters/gcp/vertex_search.py`
hardcodes `_MODEL = "gemini-3.1-flash-lite"` as a module constant while its two
sibling adapters take the model injected from `GEMINI_MODEL_LITE`. Setting that
variable does not change the grounding model, and nothing says so. Injecting it
is a prerequisite for ever acting on the paragraph above, because a pin that
cannot be changed by configuration has to be changed by a deploy.

The decision itself stands. The models are still right for now; the clock is
recorded, and one of the two pins was not honestly injectable.
