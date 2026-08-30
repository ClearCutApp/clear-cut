# ADR 0001: Product name is ClearCut

Status: Accepted
Date: 2026-08-29

## Context

The legacy documents name the product three different ways. The README and one
planning doc call it ClearCut, three docs call it IP Guardian, and the
architecture doc calls it the "IP-Clearance Agentic Engine". Anyone reading
across the docs has to guess whether these are one product or three, and the
hackathon submission form asks for a single name.

## Decision

The product is ClearCut in every new artifact. That covers the repository, the
plan/ documents, source code identifiers, the web UI, the demo, and the
submission. IP Guardian survives only as a historical name inside resources/,
where the original downloaded documents keep it.

## Consequences

New readers meet one name and can search the repo for it. The pitch materials
in resources/ still carry IP Guardian and the engine name; we cite them as
source material rather than rewriting them, so anyone following a citation into
resources/ hits the old names and must know they refer to ClearCut.
