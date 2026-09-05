> **Superseded source material.** This document predates the current build and is kept for its research and its history. Where it disagrees with a record in `docs/plan/adr/`, the ADR is right. See `docs/plan/adr/README.md`.
>
> Historical one-pager, under the former product name (ADR 0001). Names
> `gemini-1.5-pro` (retired, ADR 0002), ClickHouse as the vector memory
> database (BigQuery, ADR 0004), and `python app.py` on `localhost:5000`
> (Cloud Run on port 8080, ADR 0010).

 GOOGLE CLOUD GEMINI 1.5 PRO             PARALLEL SEARCH API      CLICKHOUSE ENGINE



IP GUARDIAN
Agentic Script Clearance, Territorial Procedural Compliance & Lore Continuity Engine

Hackathon: Agentic Cinema: The Blockbuster Hackathon (Devpost) | License: Apache 2.0 Open Source




  1. Devpost Submission & Executive Summary
IP Guardian is an autonomous multi-agent platform designed to eliminate legal risk and narrative inconsistencies for
independent film, TV, and gaming productions. Independent studios (PyMEs) lack dedicated legal teams and face
prohibitive costs ($3,000–$10,000 USD) for traditional E&O (Errors & Omissions) script clearance. IP Guardian
automates 6-category IP extraction, executes live territorial searches across 10 major global jurisdictions, and audits
script continuity against project bibles.

  Hackathon Submission Pitch
    • Inspiration: Independent filmmakers face financial ruin from unexpected IP lawsuits or missing location/music
      releases. E&O insurers require complete clearance reports that PyMEs cannot afford.
    • Core Functionality: Extracts 6 IP categories (Copyright, Trademarks, Personality Rights, Music, Locations,
      Conexity Rights). Generates actionable steps, direct agency contacts, licensing guidelines, contract templates,
      and outreach emails.
    • Territorial Engine: Tailors legal workflows for 10 countries (USA, UK, Canada, Spain, France, Mexico, Argentina,
      Brazil, India, South Korea) or defaults to International Standards.
    • Lore Guardian Module: Cross-checks incoming scripts against a vector-indexed Project Bible stored in
      ClickHouse to identify plot holes, timeline errors, and policy violations.



  2. Architecture & Runtime Partner Integration
IP Guardian strictly satisfies hackathon rules by calling real runtime SDKs for Google Cloud and Partners:

 Component             SDK / Code Hook                           Runtime Responsibility


 Google Cloud          google-genai (genai.Client)               Multimodal script analysis, structured JSON IP extraction, lore
 Gemini                                                          cross-checking, and email drafting.

 Parallel Search       requests.post('api.parallel.ai')          Runtime web search retrieving live rights holder contacts,
 API                                                             local agency links, and current licensing rules.

 ClickHouse            clickhouse-connect                        Vector memory database storing Project Bible rules and
 Engine                                                          character lore for vector context retrieval.




IP Guardian - Agentic Cinema Hackathon Submission                                                                      Page 1 of 2
  3. The 6-Category IP Framework & 10-Country Engine

  6 IP Categories Tracked                                       10 Supported Jurisdiction Hubs
    • Copyright: Books, scripts, artwork, props.                  • USA: US Copyright Office, E&O standard.
    • Trademarks: Vehicle badges, logos, storefronts.             • UK: UK IPO, BBC clearance guidelines.
    • Music & Sync: Background tracks, lyrics, masters.           • Canada: CanCon, CMF tax credit audit.
    • Personality Rights: Real persons, voice, likeness.          • Spain: ICAA, DNDA, SGAE licensing.
    • Locations: Private property, architectural IP.              • France: CNC, SACEM, Droit d'Auteur.
    • Conexity Rights: Performers & broadcast rights.             • Mexico: INDAUTOR, SACM rights.
                                                                  • Argentina: DNDA, SADAIC, ARGENTORES.
                                                                  • Brazil: ANCINE, ECAD music rules.
                                                                  • India: IPR India, regional boards.
                                                                  • South Korea: KCCA, OTT guidelines.




  4. Lore & Internal Compliance Module
When a script is uploaded alongside a Project Bible, the Lore Guardian module:

 • Indexes Project Bibles: Stores character bios, backstory timelines, and target audience protocols (e.g., PG-13
   guidelines) in ClickHouse.
 • Detects Plot Holes: Identifies contradictions between episode scripts (e.g., character backstory shifts or deceased
   characters appearing).
 • Audits Compliance: Flags unauthorized explicit content or tone shifts relative to studio guidelines.


  5. Quickstart & Open Source Execution

  # Clone repository & install dependencies
  pip install -r requirements.txt

  # Run web application
  python app.py

  # Access local server dashboard at http://localhost:5000




IP Guardian - Agentic Cinema Hackathon Submission                                                              Page 2 of 2
