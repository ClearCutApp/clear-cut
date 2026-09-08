> Historical reference. Recovery specification and workflow in `AGENTS.md` and
> `docs/recovery/` supersede conflicting instructions and completion claims.

# Agentic Workflow

This document defines ClearCut's agent topology and orchestration: what each
agent does, which model it runs, which stores it reads and writes, and how a
script moves from upload to a cleared tracker. Code structure lives in
`docs/plan/sdd.md`.

## 1. Topology

ClearCut runs on Gemini models. The orchestrator is implemented by the
AnalyzeScript use case inside the Flask service, not a separately deployed
agent; Google Cloud Agent Builder hosts one component, the project Q&A agent.
The orchestrator accepts two inputs, a full script on first upload or a delta
set of changed scenes on every later version. It parses the script into
scenes, computes a content hash per scene, groups scenes into batches of
eight, and fans the batches out to three analysis agents that run in
parallel. It gathers their findings into one normalized record set, calls the
research agent and the legislation agent once per finding that needs them,
writes tracker rows to ClickHouse, and exposes the action agents and the Q&A
agent to the dashboard.

```
        script v1 upload                     script v2+ delta
               |                                    |
               v                                    v
      +-------------------------------------------------------+
      |    Orchestrator (AnalyzeScript use case, Flask)       |
      |    parse scenes, hash, batch, dispatch                |
      +-------------------------------------------------------+
            |                   |                   |
            v                   v                   v
   +----------------+  +----------------+  +----------------+
   | Rights and IP  |  | Continuity and |  | Policy and     |
   | agent          |  | lore agent     |  | ratings agent  |
   +----------------+  +----------------+  +----------------+
            \                   |                   /
             v                  v                  v
      +-------------------------------------------------------+
      |     Finding gatherer: normalize, dedupe by asset      |
      +-------------------------------------------------------+
                  |                            |
          per rights finding          per finding needing law
                  v                            v
      +--------------------+       +------------------------+
      | Research agent     |       | Legislation agent      |
      | (Parallel Task API)|       | (Vertex AI Search)     |
      +--------------------+       +------------------------+
                  \                            /
                   v                          v
      +-------------------------------------------------------+
      |             Tracker writes (ClickHouse)               |
      +-------------------------------------------------------+
                              |
                              v
      +-------------------------------------------------------+
      |             Dashboard (control plane)                 |
      |   action agents (drafts,      Q&A agent (grounded,    |
      |   links, notifications)       cited answers)          |
      +-------------------------------------------------------+
```

The analysis agents never call each other, and the orchestrator is the only
agent that sees the whole script. Every other agent sees a scene batch, one
finding, or one tracker item. The gatherer dedupes findings by asset, so a
brand that appears in 14 scenes becomes one tracker item with 14 scene
references, and outreach happens once per asset rather than once per mention.

## 2. Analysis agents

The orchestrator sends every scene batch to all three analysis agents. The
rights and policy agents process a batch in one model call each; the
continuity agent makes one call per scene, because its retrieval context is
scene-specific and gemini-3.1-flash-lite keeps the per-call cost low.

### 2.1 Rights and IP agent

Runs gemini-3.7-flash. It scans each scene batch for elements in the six
rights categories: industrial property (brands, logos, protected product
designs), pre-existing and musical works (songs, artwork, books, footage
shown on screen), personality and image rights (talent, extras, real
people), integrated visual works (wardrobe, character designs, original
props, typefaces), locations (private premises and public spaces that need
permits), and elements under special laws (flags, uniforms, currency).

Every detected element gets a tag from the NER taxonomy: [BRAND],
[MUSIC_EXISTING], [MUSIC_ORIGINAL], [ART_LIT], [MEDIA_AV],
[TALENT_CHARACTER], [REAL_PERSON], [PROPS_DESIGN], [LOCATION_PRIV],
[LOCATION_PUB], [SPECIAL_SYMBOL]. The agent also reads intent verbs (wears,
plays, reads, enters) to separate an incidental mention from a use that
needs clearance.

Output is pinned by `response_schema`: each call returns a JSON array of
finding objects carrying scene id, tag, category, quoted script text, risk
level, and the document the clearance needs (sync license, location release,
talent release, work-for-hire assignment). The Gemini API enforces the
schema, so the gatherer never parses free text.

### 2.2 Continuity and lore agent

Runs gemini-3.1-flash-lite once per scene. For each scene it retrieves up to
12 Project Bible chunks and prior-episode facts from BigQueryVectorStore and
answers one question: does this scene contradict any retrieved fact? A
contradiction becomes a finding that cites both sides, for example "Episode 4
page 8 has the character say his father died during his childhood; Episode 1
page 4 established the father lives abroad." The agent judges the scene only
against retrieved text; when retrieval returns nothing relevant it records
no finding instead of speculating.

### 2.3 Policy and ratings agent

Runs gemini-3.7-flash per scene batch, retrieving the production's rule
set from the same BigQueryVectorStore index the continuity agent uses. It
checks three rule families: age-rating constraints (a production targeting an
R13 rating gets findings for profanity, explicit violence, and substance
use), brand and sponsor guidelines from the bible (a placement contract with
one soft-drink brand turns a rival brand's appearance into a finding), and
tone rules such as no alcohol on screen in children's programming. Each
finding cites the rule it violates and the scene page.

## 3. Research agent

Runs once per rights finding, after the fan-out completes. It calls the
Parallel Task API with three questions about the finding's asset: who owns
it, who represents the owner, and whether the rights holder has a record of
litigation over similar uses. Parallel returns each answer as a claim with
citations and a per-claim confidence level, and ClearCut maps that confidence
onto the finding's risk rating. A high-confidence ownership claim leaves the
model-assigned risk in place, a medium-confidence claim raises the risk one
step, and a low-confidence claim marks the finding unverified and escalates
it to human review. A claim without a citation is dropped. The surviving
answers (rights holder, representative, contact, litigation posture, sources)
write into the finding's tracker row, where the outreach drafter later reads
them.

## 4. Legislation agent

One Vertex AI Search data store holds the legal corpus: statutes, regulator
guidance, and collective management society procedures for the ten supported
jurisdictions (Argentina, the United States, Spain/EU, Mexico, Canada,
France, the United Kingdom, India, Brazil, South Korea). Every document
carries jurisdiction metadata. When a finding needs legal grounding, which
license a sync use requires in Mexico or whether a landmark's night lighting
is protected in France, the legislation agent queries the store with a
metadata filter restricted to the production's declared territories, so an
Argentina-Mexico co-production never receives an answer sourced from US
doctrine.

Every answer carries groundingMetadata citations, and the dashboard renders
them next to the finding. When the filtered store returns no grounded
passage, the agent answers that no grounded source was found and the item
escalates to counsel. It never fills the gap from model weights.

## 5. Action agents

Four agents sit behind the dashboard and run when the producer triggers them
on a tracker item, with one exception: the notification sender also fires
automatically on delta regressions. Notifications are internal alerts to the
production team, never outbound legal mail, so the draft-approval rule below
is untouched.

- Outreach email drafter. Drafts the license or permission request from the
  rights holder and contact the research agent stored, using a template per
  rights category and the jurisdiction specifics the legislation agent
  grounded (an Argentine sync request addresses SADAIC's synchronization
  department, a US one names the publisher found through Songview).
- Solicitation document drafter. Drafts formal instruments: location
  releases, talent releases, work-for-hire assignments, and registration
  filings for the production's own IP.
- Stakeholder link resolver. Resolves the rights holder's registry or
  contact link from what the research agent stored and attaches it to the
  tracker item; the dashboard opens it.
- Notification sender. Sends state-change and regression notices to the
  linked stakeholders.

ClearCut drafts legal correspondence and never sends it. The producer opens
the draft on the dashboard, edits it, and approves it; only then does the
message leave the system. Approving an outreach draft moves the tracker item
from BLOCKED (0%) to IN_PROGRESS (50%). When the signed permission or
license arrives and the producer records it against the item, the item moves
to CLEARED (100%). No agent performs either transition on its own.

## 6. Project Q&A agent

A conversational text agent over tracker state in ClickHouse, findings, lore
in BigQueryVectorStore, and the legislation store when a question touches
law. "What is still blocking release in Mexico?" becomes a ClickHouse query
for BLOCKED items whose jurisdiction set includes Mexico, and the answer
lists each item with its scene pages and required documents. "Can we show
the mural in scene 12?" pulls the finding, the research claims, and grounded
Mexican law, each with its citation. The agent is read-only; it answers
questions and never changes tracker state or triggers an action agent.

## 7. The continuous loop

Script v2 arrives. The parser splits it into scenes and computes each
scene's content hash, SHA-256 over the normalized scene text with whitespace
collapsed. Scenes whose hash matches the stored hash skip analysis; changed
and new scenes re-enter the fan-out as a delta batch. A revision that
touches 6 of 55 scenes costs 6 scenes of analysis, and ClickHouse records
the hash set per version so every run is attributable to a script version.

Tracker reconciliation runs after the delta pass. Items on unchanged scenes
carry forward untouched, permissions included. Two cases get specific
handling:

- A changed scene with a CLEARED item flags that item for human re-review.
  The permission was negotiated against the old text; if the sync license
  covered 15 seconds of background radio and the revision moves the song to
  a title sequence, the license may no longer fit. The item keeps its
  CLEARED state but wears the re-review flag until the producer confirms or
  reopens it.
- A regression, meaning an item that returns to BLOCKED or a new critical
  finding on a previously clean scene, fires the notification sender
  automatically, without a producer trigger. The notice is an internal alert
  to the production team, never outbound legal mail.

The dashboard is the control plane. Every state transition and every action
trigger flows through it: agents propose findings and drafts, ClickHouse
records state and version history, and the producer takes every decision
that changes an item's state.

## 8. Guardrails

- No uncited legal claims. A legislation answer without groundingMetadata
  citations is discarded and the item escalates; a research claim without a
  Parallel citation is dropped before it reaches the tracker.
- Confidence gates. A low-confidence Parallel claim, or an analysis finding
  the model rates below 0.7 confidence, escalates to human review instead of
  settling a risk rating on its own.
- Drafts, never advice. Agents produce findings and drafts. Nothing they
  output is final legal advice, and every draft carries an unreviewed banner
  until the producer approves it.
- Cost ceilings. Each scene is capped at 8,000 input tokens (scene text plus
  at most 12 retrieved chunks) and 1,500 output tokens per analysis agent. A
  120-page feature parses to roughly 55 scenes, so a full first pass has a
  fixed worst case and a delta pass costs only the changed scenes. Analysis
  agents hold no loop of their own; the orchestrator invokes them per batch,
  so a malformed scene cannot spin an agent into repeated calls.

## 9. Boundaries

This document owns agent topology and orchestration; `docs/plan/sdd.md` owns code
structure, and the two meet at the ports. Script parsing and page anchors
ride ScriptIngestion, and scene hashing happens in the AnalyzeScript and
EvaluateDelta use cases. The Rights and IP and Policy agents ride
SceneExtractor; the Continuity agent rides LoreStore. The research agent
rides RightsResearch, the legislation agent rides LegalGrounding, the action
agents ride Notifier and TrackerStore, and the Q&A agent rides LoreStore,
LegalGrounding, and TrackerStore. When an agent's behavior changes here, the
change lands in one port implementation there.
