# **[https://agentic-cinema.devpost.com/](https://agentic-cinema.devpost.com/)**

# **Technical Architecture and Framing for the "Agentic Cinema" Hackathon**

The **"Agentic Cinema: The Blockbuster Hackathon" (Google Cloud + Devpost)** hackathon requires building an autonomous multi-agent system focused on the entertainment industry. Our solution, the **IP-Clearance & Asset Protection Engine**, combines Google Cloud's core infrastructure with partner technologies integrated via the Model Context Protocol (MCP) and REST APIs to handle the complete legal management of an independent production.

### **Vision and Integrated Technical Scope**

The system does not operate as a traditional conversational assistant over PDF files; instead, it functions as an **autonomous, deterministic agentic network** that proactively manages two parallel workflows:

- **Third-Party IP Management (Clearance & Licensing):** Scanning of trademarks, musical works, likeness/image rights, and locations in the text or attachments → active search for the actual rights holders → drafting of license requests (*Outreach*).

- **Protection of Own IP (IP Creation Engine & Defensive Registration):** Scanning of unpublished scripts, series bibles, character designs (PNG), and original music → drafting of talent assignment contracts (*Work for Hire*) → assembly of the registration deposit package adapted to the relevant jurisdiction (DNDA, USCO, INDAUTOR, etc.).

- **Dynamic Scalability Module (Incremental Delta Evaluation):** As the production evolves and new versions are uploaded (script_v2.pdf or new attachments), the AI evaluates only the differences (deltas) between versions, recalculating the new risks without losing the history or the previously obtained permissions.

The following details how our project (**"IP-Clearance Agentic Engine"**) fits within the competition and what role each partner plays.

### **1. Technology Core (Google Cloud Core)**

- **Google Cloud Agent Builder & Gemini 1.5/2.0 Enterprise:**

  - Acts as the **Main Orchestrator Agent (*Digital Entertainment Lawyer*)**.

  - Processes the script text (PDF, Final Draft).

  - Runs natural language processing (NLP) with legal *Named Entity Recognition* (NER) to classify and apply the taxonomy of events across 6 IP categories, and coordinates execution of the auxiliary tools via Function Calling / MCP.

  - Handles computer vision (CV) for logos/designs and audio analysis for phonograms.

  - Runs the incremental version comparison (deltas) and drafts the automated legal documentation (requests, *Work for Hire* contracts, and registration packages).

- **Google Cloud Storage (GCS):**

  - Secure, immutable storage for uploaded scripts, design attachments (images/audio), and signed contracts/documents.

### **2. Hackathon Partner Service Mapping (Track Selection)**

To comply with the competition rules and compete for the technology partners' specific prizes, we need to select the main track and properly integrate the ecosystem's tools:

| **Hackathon Partner** | **Specific Role on Our Platform** | **Required Technical Integration** |
|---|---|---|
| **PARALLEL** *(Recommended as Main Partner Track)* | **Real-time engine for tracking rights holders and public registries.**<br><br>**Actions:**<br>- **Third-party music:** Queries public and registry databases (ASCAP, BMI, SADAIC, etc.) to identify publishers and record labels.<br>- **Brand Clearance:** Scans corporate directories and global trademark databases (WIPO, USPTO, INPI) to find the corporate name and the contacts of the legal or marketing department.<br>- **Image Rights/Talent:** Locates representation agencies (CAA, UTA, etc.) when real people or celebrities are mentioned. | Integration via the **Parallel Search API / Parallel Web Search MCP Server**, called directly by the Gemini agent when identifying who to send the *outreach templates* to. |
| **CLICKHOUSE** *(Analytics Track Alternative)* | **Database, state persistence, event history, and Compliance Tracker Dashboard engine.**<br><br>**Actions:**<br>- Stores, in an analytical and hyper-fast way, the regularization status of each script event by scene, feeding the dynamic Tracker for each IP item per scene in JSON: **🔴 0% (Pending)**, **🟡 50% (In Progress)**, **🟢 100% (Regularized/Signed)**.<br>- Performs instant analytical calculations to power the status indicators and the platform's overall progress percentages.<br>- Records version history to associate deltas with each specific script version. | Connection to **ClickHouse Cloud**, where the agent writes the status of each item (JSON) to calculate real-time metrics across multiple productions. |
| **REPLIT** | **Hosting, user interface, prototyping, and end-to-end deployment of the full-stack application.**<br><br>**Actions:**<br>- Hosts the frontend of the interactive web application (dashboard with status indicators) that consumes the agentic network's API, connecting automatically to Google Cloud and generating the public URL required for submission.<br>- Renders the **Compliance Tracker Dashboard** (status indicators, progress bar, and document downloads).<br>- Manages the incremental ingestion of scripts and attachments through direct interaction with GCS and Gemini. | Deployment via **Replit Agent** and public hosting of the end-to-end solution. |
| **GRAFANA LABS** | **Multi-agent network health monitoring, and telemetry for latency, token consumption, and agent accuracy via OpenTelemetry.**<br><br>Generates visual metric dashboards on latency, API costs, and the accuracy rate of red-flag IP detection within the script. | Telemetry integrated with OpenTelemetry, sent to Grafana. |
| **IBM** | **Legal governance and risk assessment agent. Secondary agent (via watsonx / IBM Granite MCP) for auditing Fair Use policies and legal co-ownership risks.**<br><br>Uses IBM Granite / watsonx as a secondary agent specialized in cross-checking local privacy and copyright policies. | Development of the agentic flow using **IBM Bob** / IBM's MCP Server. |

### **3. Action Coverage Matrix**

| **Operational Action** | **Tool / Responsible Partner** | **Technology Applied** |
|---|---|---|
| **Script Reading and IP Classification** | Google Cloud (Gemini) | LLM + Legal NER |
| **Incremental Delta Evaluation (v1 vs v2)** | Google Cloud (Gemini) | Differential Context Processing |
| **Multimodal Analysis (Logos, Props, Audio)** | Google Cloud (Gemini) | Computer Vision & Audio ML |
| **Rights Holder and Legal Email Tracking** | **PARALLEL** | Parallel Search API / MCP |
| **Tracker State Persistence** | **CLICKHOUSE** | ClickHouse Cloud DB |
| **Analytics and Compliance % Calculation** | **CLICKHOUSE** | Real-Time SQL Engine |
| **Third-Party Outreach Drafting** | Google Cloud (Gemini) | Agentic Text Generation |
| **Deposit Package Assembly (Own IP)** | Google Cloud (Gemini) | Automated Legal Drafting |
| **Hosting and Interactive Frontend** | **REPLIT** | Full-Stack Web App |
| **Contract and Script Safekeeping** | Google Cloud | Cloud Storage (GCS) |

### **4. Agentic Architectural Flow in Execution (Runtime Workflow)**

1.  **Input:** The producer uploads the script or files to the platform hosted on **Replit**.

2.  **Multimodal Analysis:** **Gemini Enterprise (Google Cloud Agent Builder)** scans the content and detects risk events across 6 categories.

3.  **Active Lookup (Parallel Search API):** The agent triggers the **Parallel** tool to search the web for who the current copyright holder of a song is, or the legal representative of a trademark, returning the official contact emails.

4.  **State Logging (ClickHouse):** Each detected right is written to **ClickHouse**, recording its compliance status (e.g., *0% - Pending Submission*).

5.  **Contract and Outreach Auto-generation:** Gemini automatically drafts the requests, and the system makes them available in the interface.

6.  **Visual Metrics:** The frontend consumes data from ClickHouse to display the regularization status indicator on screen.

[ SCRIPT v1 / ATTACHMENTS ] ────► ( Upload on REPLIT ) ────► [ Storage on GCS ]

│ │

▼ ▼

┌─────────────────────────────────────────────────────────────────────────────────────────┐

│ GOOGLE CLOUD AGENT BUILDER (GEMINI Core) │

│ 1. NER Breakdown (6 Categories) │ 2. Delta Comparison (v1 vs v2) │

└────────────────────────────┬──────────────────────────────────────┬─────────────────────┘

│ │

(If Third-Party IP) │ │ (If Own IP)

▼ ▼

┌──────────────────────────────┐ ┌──────────────────────────────┐

│ PARALLEL SEARCH API │ │ GEMINI LEGAL GENERATOR │

│ Autonomous search for │ │ Generation of the DNDA/USCO │

│ rights holders, publishers, │ │ deposit package + WFH. │

│ and emails. │ │ │

└──────────────┬───────────────┘ └──────────────┬───────────────┘

│ │

└───────────────────┬──────────────────┘

▼

┌──────────────────────────────┐

│ CLICKHOUSE CLOUD │

│ Storage of JSON and │

│ status calculation (🔴 / 🟡 / 🟢). │

└──────────────┬───────────────┘

▼

┌──────────────────────────────┐

│ REPLIT INTERFACE │

│ Tracker visualization and │

│ download of Outreach │

│ messages/Emails. │

└──────────────────────────────┘

### **5. Strategic Framing for Devpost Judges**

To maximize the score in the Hackathon evaluation (Technology, Design, Impact, and Creativity):

- **Real enterprise value:** We solve an operational problem that costs the audiovisual industry millions of dollars: legal uncertainty and the high costs of E&O (*Errors and Omissions*) insurance audits.

- **Demonstration of Autonomous Agentic Architecture:** Combines an intelligent orchestrator (**Gemini**), a real-time web search execution agent (**Parallel**), and a deterministic analytical database (**ClickHouse**).

- **Strict compliance with the Hackathon requirements:** This is not a simple "chat with a PDF." It is a **deterministic and autonomous multi-agent network** that performs real operational tasks (breakdown, external search with Parallel, analytical writes to ClickHouse, and legal documentation generation), thereby strictly meeting the requirement to use the **Google Cloud** core, enhanced through runtime integrations with the official **Partners**.

---

### **Hackathon Requirements Compliance Summary (Devpost & Rules)**

| **Hackathon Requirement** | **Status** | **Platform Implementation** |
|---|---|---|
| **Google Cloud Runtime Usage** | **Met** | Integrated via the official google-genai library, using the genai.Client client with the gemini-1.5-pro model in app.py. |
| **Partner Runtime Usage** | **Met** | 1. **Parallel Search API**: Real API call at runtime with requests.post() to search for rights holders and local agencies.<br><br>2. **ClickHouse**: Native connection with clickhouse-connect for the vector database of lore and compliance. |
| **Detectable Open Source License** | **Met** | LICENSE file under the **Apache License 2.0** at the root of the repository (automatically recognized by GitHub in the *About* section). |
| **Local Execution Instructions** | **Met** | Included in the README.md and documented for execution with Flask or compilation into a single .exe. |
| **6 IP Category Modules** | **Met** | Structured JSON detection of: *Copyright, Trademarks, Image/Personality Rights, Music and Sync, Locations and Architecture, and Related Rights*. |
| **10-Country Territorial Framework** | **Met** | Interactive dropdown menu with: US (US Copyright), United Kingdom (UK IPO), Canada (CanCon), Spain (ICAA/SGAE), France (CNC/SACEM), Mexico (INDAUTOR), Argentina (DNDA/SADAIC), Brazil (ANCINE), India (IPR), South Korea (KCCA), and International Standard. |
| **Compliance & Lore Bible Module** | **Met** | Context box in the interface and backend integration that cross-checks the script against character, age, and backstory rules. |
