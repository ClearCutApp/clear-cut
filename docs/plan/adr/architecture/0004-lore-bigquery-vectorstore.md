# ADR 0004: BigQueryVectorStore for Project Bible continuity

Status: Accepted
Date: 2026-08-29

## Context

The legacy design hand-rolls vectorization and cosine similarity for Project
Bible continuity checks, which leaves us maintaining custom embedding calls, a
custom table schema, and custom similarity math.

## Decision

Continuity lookups use BigQueryVectorStore from langchain-google-community. The
class delegates embedding to an injected embedder, auto-creates its dataset and
table, and brute-force scans below 5,000 rows, which covers our scale; above
that threshold it builds an IVF index automatically. Chunking stays ours, one
chunk per scene. Project isolation runs through metadata filters. When the dict
filter's equality semantics are too narrow, we drop to the raw SQL filter
string. We never filter on float columns, because float equality needs an
epsilon comparison the filter does not perform.

## Consequences

We take a LangChain dependency for one class. If its filter semantics fight the
clearance queries, the exit is raw SQL against the same table rather than a
migration to a new store.
