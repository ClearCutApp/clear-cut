# ADR 0005: One Vertex AI Search data store for territorial grounding

Status: Accepted
Date: 2026-08-29

## Context

The legacy approach pastes jurisdiction rules into the prompt string ("Under
{country} jurisdiction...") and leaves the model to invent the rest. Invented
law in a clearance finding is worse than no finding.

## Decision

Territorial legal grounding runs through one Vertex AI Search data store over
gs://clearcut-legal-corpus/, with one GCS prefix per jurisdiction and a
jurisdiction metadata field filtered at query time. One store with a filter
replaces both the ten per-country stores and the prompt-stuffed rules. Grounded
answers return groundingMetadata with groundingChunks and groundingSupports, so
every legal claim in a finding carries a citation to its source document. That
citation trail makes a finding usable in an errors-and-omissions insurance
conversation.

## Consequences

Filters only work after the jurisdiction field is marked Indexable by hand in
the console schema tab, a step nobody automates and everybody forgets once.
Corpus quality bounds answer quality; an empty prefix for a jurisdiction yields
an honest "no grounded answer" instead of invention.
