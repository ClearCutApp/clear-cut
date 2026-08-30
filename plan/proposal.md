# ClearCut: Proposal

ClearCut is an agentic clearance platform for cinema scripts. The producer uploads a screenplay; ClearCut finds everything that could stop the film's release and gives the producer a way to resolve each item from one dashboard. Target: the Agentic Cinema hackathon, deadline September 7, 2026.

## The problem

No film reaches theaters or a streaming platform in the US, Canada, or the UK without Errors & Omissions insurance, and insurers write those policies to an industry standard of $1,000,000 per claim and $3,000,000 aggregate, with a deductible between $10,000 and $25,000. Getting the policy requires a script clearance report, for which a specialized entertainment lawyer charges $3,000 to $10,000 per script.

The deductible is the trap for a small production company. When a rights holder sends a $15,000 demand letter over a background song, the insurer pays nothing and the producer covers all of it, so a single minor claim, even an unfounded one, costs an independent producer $10,000 to $25,000 in deductible and legal fees. Claims are not rare. Roughly one in eight independent productions (12 to 15 percent) receives at least one formal IP claim or demand letter when the project is shown to buyers. Music synchronization drives about 40 percent of those claims, on-screen trademarks 25 percent, likeness and real-people issues 20 percent, and background artwork 15 percent.

When a claim escalates, defending it in a US federal court averages $75,000 to $350,000 before trial and can exceed $1.4 million at full trial, which is why more than 90 percent of cases settle out of court. The injunction is worse than the fine. A rights holder who files two weeks before a festival premiere or platform launch can freeze the release, so producers pay $30,000 settlements rather than lose a $500,000 distribution deal, and injunctions have frozen distribution deals at the $10 million scale.

A studio absorbs all of this with a clearance department. A five-person production company in Madrid or Guadalajara finds out about the Wonderwall needle-drop in scene 14 when the distributor asks for the E&O certificate, at the point where every fix is most expensive.

## The gap

Existing tools each cover one slice of the problem, and none connects detection to resolution.

| Player | What it does | Where it stops |
|---|---|---|
| Prescene.ai | AI script reports across six clearance categories (brands, trademarks, celebrities, music, copyrighted works, fictional universes) | Hands back a PDF ("An iPhone is mentioned on page 12, Medium Risk") with no fix path; 90 percent of the product is script coverage for story analysis |
| Filmustage | AI script breakdown for logistics (props, wardrobe, VFX) plus basic copyright alerts | Built for scheduling and budgets, not legal state; no rights-holder identification, no procedure tracking |
| TNCCC, IndieClear, Clearance Unlimited | The clearance reports E&O insurers accept, produced by lawyers with software assistance | $1,500 to $3,000+ per report, one to seven days of turnaround, and the deliverable is a static PDF that ages the moment the script changes |
| FilmTrack, Rightsline | Manage rights and licenses the production already acquired | Never read the script; they track what the producer already knows about |
| Songtradr, Artlist | Search and license music and stock assets | Disconnected from the script; they cannot say which scenes need a license |

Prescene and Filmustage both use "IP protection" in their marketing to mean the uploaded script will not leak (TPN and SOC 2 compliance), not that the script's contents get cleared. No player drafts the outreach email to a music publisher, tracks whether the rights holder answered, or carries cleared items forward when script v2 arrives. ClearCut covers exactly that loop.

## The product

The producer uploads a screenplay and ClearCut renders it in ScriptView with findings overlaid inline on the text, the way Grammarly marks prose. The bar scene where Wonderwall plays gets a music-rights flag on that line; the FC Barcelona jersey in a wardrobe description gets a trademark flag. Detection runs across six rights categories: industrial property and brands; pre-existing and musical works; personality, image, and privacy; integrated visual works; locations and permits; special laws and national symbols.

Each finding carries three things. First, the law it triggers, cited for the production's declared territories, so a Spanish co-production sees the Spanish provision rather than a US generality. Second, who holds the rights, resolved by live research with sources instead of model memory. Third, an action the producer can execute from the TrackerDashboard: draft an outreach email to the rights holder, generate a solicitation document, open the stakeholder's registry or contact link, ask about current legislation for the production's territories (this opens ProjectQA pre-filled with the territory question, answered through the existing question endpoint), or send a notification to a team member. ClearCut drafts legal correspondence and never sends it; the producer reads, edits, and approves every message from the dashboard before anything leaves the system.

Every finding sits in one of three tracker states, BLOCKED (0%), IN_PROGRESS (50%), or CLEARED (100%), and the project rolls up to a single clearance percentage. When the writer delivers script v2, ClearCut re-analyzes only the scenes that changed; a sync license obtained for scene 14 carries forward untouched when scene 30 is rewritten. ProjectQA, the third surface, is a conversational agent over the project state that answers questions like "what still blocks a Mexico release?" or "have we heard back on the Hotel California request?"

The shareable output, planned as the first post-hackathon roadmap item, is the IP Passport, a due-diligence page with an IP Health Index (78/100 on the demo project) behind a secure URL, so a distributor, festival, or insurer checks the production's rights status in one click instead of requesting a document package. The producer still hires a lawyer for the E&O sign-off, and hands over an organized clearance file instead of a shoebox of emails.

The frontend is a React + Vite + Tailwind SPA carrying those three surfaces, and the whole system ships as one Cloud Run service.

## Hackathon fit

The build sits on Gemini and Google Cloud Agent Builder. gemini-3.7-flash extracts structured findings from scene batches into the six categories; gemini-3.1-flash-lite runs the per-scene bible checks that keep delta evaluation affordable on every script revision.

We chose the Parallel partner track because rights-holder research is the exact shape of work Parallel's Task API does well. "Who administers the synchronization rights to Hotel California in Spain" needs an answer with per-claim citations and calibrated confidence, because the producer will send a legal request based on it; a plausible unsourced answer is worse than none. ClearCut's research agent calls Parallel through its MCP server at https://search.parallel.ai/mcp and stores each citation alongside the finding it supports. Every agent run emits OpenTelemetry traces to Grafana Cloud, so token spend, latency, and per-stage failures stay visible during judging and after.

Against the four judging criteria, technological implementation is the extraction pipeline, delta evaluation, and cited research; product design is the inline ScriptView experience plus the approval gate on all correspondence; potential impact is the $10,000 to $25,000 claim floor landing on the producers least able to pay it; quality of idea is the category gap the benchmark documents.

The demo runs three minutes. We upload a planted 12-page script containing a Ferrari Testarossa, the song "Hotel California," and one contradiction against the project bible. All three findings surface in ScriptView with page numbers inside the first minute. We open the Hotel California finding, show the Parallel-sourced rights-holder record with its citations, draft the outreach email on camera, approve it as the producer, and watch the tracker row move from BLOCKED to IN_PROGRESS. The final thirty seconds show the Grafana dashboard tracing that exact run, stage by stage.

## Go-to-market

Phase 1 targets Spanish-speaking independent producers in Spain, Mexico, and Argentina: roughly 6,700 audiovisual companies in Spain, 1,200 to 1,400 in Mexico, and 800 to 1,000 in Argentina. The pressure in these markets already exists and goes unserved in Spanish. Netflix and ViX impose IP audits before acquiring Mexican catalog content, Spain's ICAA ties public funding to chain-of-title rigor, and Argentine producers face distribution blocks from SADAIC and ARGENTORES claims, yet the clearance agencies serving this work operate in English at US prices. ClearCut ships with the local registry links (OEPM, INDAUTOR, DNDA) and drafts correspondence in Spanish.

Phase 2 moves to the US indie sector and Canada, roughly 25,000 to 30,000 and 3,500 to 4,500 target companies respectively, where E&O insurance is mandatory for distribution and producers already pay for software. Phase 1 supplies the entry evidence for that market: real Spanish-language productions cleared through the tracker, each with territory-cited findings and an IP Passport a US insurer can audit.
