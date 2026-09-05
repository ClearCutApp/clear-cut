> **The authoritative rights taxonomy.** The six IP categories, the eleven NER
> labels and the `EVT-NNN` identifier shape in `domain/finding.py` and
> `domain/taxonomy.py` implement this document faithfully. The domain carries
> eight categories, not six: CONTINUITY and POLICY are ours, not this file's.
> Its coloured status circles predate `.claude/WRITING.md`, which requires the
> words BLOCKED, IN_PROGRESS and CLEARED instead.

# **Artificial Intelligence Architecture for IP Management and Local/Global Actionability**

For the AI model to process the script or attached material and act as
a regularization manager, it is structured into **two major work
engines**:

1.  **Legal Inference Engine:** Detects and identifies the rights
    involved.

2.  **Territorial Actionability Engine (Country Orchestrator):**
    Queries the case-law and regulatory database of the production's
    main base (and co-production countries) to indicate the exact
    regularization workflow.

**Legal Inference Engine**

To train the AI model to perform comprehensive rights detection and
mapping, we cannot limit ourselves to traditional Intellectual
Property assets (such as trademarks or copyright over texts). In an
audiovisual production, **Intellectual Property (Copyright and
Industrial Property)**, **Related Rights**, **Personality and Image
Rights**, **Real Property Rights and Location Contracting**, and
**Civil Liability / Defamation Risks** all converge.

The AI model must act as a "Digital Entertainment Lawyer" overseeing
6 major categories of rights.

### **Categorization of Rights to Detect and AI Mapping Logic**

#### **1. Industrial Property (Trademarks, Patents, and Designs)**

- **Elements to Detect in the Script / Materials:**

  - Real brand names (e.g., *"He pulls out an Apple/iPhone"*,
    *"He drinks a Coca-Cola"*).

  - Logos visible in visual descriptions or art design.

  - Protected industrial designs (e.g., a car's characteristic
    silhouette, an iconic designer chair, clothing from recognized
    brands).

- **AI Mapping Mechanism:**

  - **Risk Category:** Third-Party Trademark.

  - **Legal Requirement:** *Brand Clearance* / Trademark Use License
    (Product Placement vs. commercial Fair Use).

  - **Suggested Action:** Draft an authorization request to the
    brand's marketing/legal department or suggest replacing it with a
    fictitious brand (*greeking*).

#### **2. Intellectual Property – Pre-Existing and Musical Works (Copyright)**

- **Elements to Detect:**

  - **Existing music:** Mentions of songs, lyric fragments, playback
    on radios or car radios (e.g., *"'Thriller' by Michael Jackson
    plays in the background"*).

  - **Original music:** Scenes where the script indicates *"The
    character plays an original melody on the piano"* or *"Score
    composed for the scene"*.

  - **Works of art and literature:** Paintings hanging in locations,
    sculptures, signed graffiti, readings from protected books,
    poetry.

  - **Audiovisual within audiovisual:** TVs turned on showing other
    movies, video games being played on screen, news clips.

- **AI Mapping Mechanism:**

  - **If Third-Party:** Separate composition rights (Master /
    Publishing) → Require a *Sync License* and a Phonogram License.

  - **If Original:** Require a *Work for Hire* Agreement with the
    composer + Deposit Registration of the Musical Work in favor of
    the production company.

#### **3. Personality, Image, and Privacy Rights (Personal Rights)**

- **Elements to Detect:**

  - **On-Screen Talent (Actors / Extras):** Any character with
    dialogue, secondary action, or background extras in crowd scenes.

  - **Real People / Biographies:** Mentions of politicians,
    celebrities, living people, or people who died recently.

  - **Voice and Likeness:** References to dubbing, voice
    impersonation, or motion capture.

- **AI Mapping Mechanism:**

  - **For Actors/Extras:** *Talent Release Agreement* (assignment of
    image, voice, and performance rights).

  - **For Real People:** *Life Rights Agreement* or a Privacy
    Invasion / Defamation Risk Assessment (*Defamation/Libel Check*).

#### **4. Integrated Visual Works and Production Elements (Art, Wardrobe, and Graphics)**

- **Elements to Detect:**

  - Unique wardrobe designs (e.g., superhero or monster costumes),
    character design (*Character Design* in animation or video
    games).

  - Highly elaborate props with original design.

  - Software captured on screen, fictitious graphic interfaces (UI/UX
    created for the film), or typefaces (*Fonts*) used in the titles.

- **AI Mapping Mechanism:**

  - **Internal Designs:** Full Assignment of Rights agreement
    (*Assignment of Rights*) from the designer/artist to the
    production company.

  - **Typefaces and Software:** Verify the Commercial Film/Digital
    Use License for the typeface or software used.

#### **5. Locations, Movable/Immovable Property, and Public Domain Permits**

- **Elements to Detect:**

  - **Private Locations:** Houses, landmark buildings with protected
    architecture, commercial premises (e.g., *"Scene inside a
    Starbucks"*).

  - **Public Spaces:** Parks, streets, government buildings,
    restricted monuments (e.g., the Eiffel Tower's nighttime lighting
    is protected by rights).

- **AI Mapping Mechanism:**

  - **Private:** *Location Release Form* signed by the owner or
    administrator.

  - **Public:** Filming permits from the local Film Commission and
    payment of municipal fees.

#### **6. Elements Protected by Special Laws and National Symbols**

- **Elements to Detect:**

  - Flags, national coats of arms, security force uniforms (police,
    military), banknotes/coins (counterfeiting regulations).

- **AI Mapping Mechanism:**

  - Restricted Use Alert under State Regulation → Request
    authorization from the relevant government ministries depending
    on the country.

### **Structured Mapping Matrix of the AI Model**

To train the AI, the data extracted from the script will be processed
into the following **output structure (internal JSON)** before being
presented on the platform:

| **ID** | **Script Text / File** | **Detected IP Category** | **Potential Risk** | **Document / Contract Needed** | **Status (Tracker)** |
|---|---|---|---|---|---|
| **EVT-001** | *"Scene 4: Juan takes out a bottle of Quilmes"* | Third-Party Trademark | Medium (unsponsored brand use) | Trademark Clearance Form or Replacement (*Greeking*) | 🔴 0% (Pending) |
| **EVT-002** | *"Radio plays 'De Música Ligera'"* | Musical Copyright (Third-Party) | High (Sync Infringement) | Sync License + Master License | 🔴 0% (Pending) |
| **EVT-003** | *"Actor 1 (Pedro) has dialogue in the bar"* | Image / Performance Right | Critical (cannot be exhibited without a contract) | *Talent Release Form* / Actors' Union Contract | 🟢 100% (Signed) |
| **EVT-004** | *"Forest Monster design (Attached PNG)"* | Internal IP / Character Design | High (risk of claim from the illustrator) | Work for Hire Agreement with the Concept Artist | 🟡 50% (Sent) |

### **How Does the AI Detect This Technically?**

1.  **Natural Language Processing (NLP) for Text / Scripts:**

    - Uses **Named Entity Recognition (NER)** trained on the
      entertainment industry to automatically categorize proper
      nouns (people, places, brands, songs).

    - **Action and Intent Analysis:** Detects verbs implying
      performance or playback (e.g., *"listens to"*, *"wears"*,
      *"reads"*, *"plays"*).

2.  **Computer Vision (CV) for Attached Files (Sketches, Designs,
    Audio):**

    - **Visual Similarity Search:** Compares uploaded images (e.g., a
      character design) against global databases of trademark
      registrations and protected images to prevent inadvertent
      plagiarism.

    - **Audio Recognition (Fingerprinting):** Compares attached audio
      clips against databases such as Shazam/Audible Magic to
      determine whether the music is rights-free, library music, or
      registered.

### **Summary of the AI Structure**

The AI will take the script or attached file, **break the scene down
into IP atoms**, classify each element into 1 of the 6 categories,
and automatically generate the list of legal requirements.

Once this IP detection map is defined, the second part of **Point 2**
consists of determining **how the AI proceeds according to the
production's country** (jurisdictions, registration bodies such as
DNDA, the US Copyright Office, INPI, WIPO, local actor laws, and
rights-holder lookup).

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

To formally move into the **AI model training phase**, we need to
translate this 6-category framework into a **Training Dataset and
Prompt/Model Architecture (NLP + Vision + Audio)**.

Below is a detailed breakdown of how the technical training is
structured and the exact taxonomy used to train the model.

### **1. Labeling Taxonomy for AI Fine-Tuning (NER / Categorization)**

For the model (based on LLM/NLP) to learn to label each word or
paragraph of the script, we will use the **Named Entity Recognition
(NER)** standard adapted to Entertainment Law.

```
Extraction Tags:

- [BRAND]: Trademarks, consumer products, companies, logos mentioned.
- [MUSIC_EXISTING]: Existing songs, artists, bands, commercial radio stations.
- [MUSIC_ORIGINAL]: Explicit mention of compositions created for the work.
- [ART_LIT]: Works of art, books, sculptures, graffiti, poems.
- [MEDIA_AV]: TV shows, movies, news clips, video games shown on screen.
- [TALENT_CHARACTER]: Actors with lines, extras, stunt doubles.
- [REAL_PERSON]: Public figures, real living/deceased people, biographies.
- [PROPS_DESIGN]: Exclusive wardrobe, character designs, original props, typography.
- [LOCATION_PRIV]: Commercial establishments, private houses, architect-designed buildings.
- [LOCATION_PUB]: Parks, monuments, streets, government buildings.
- [SPECIAL_SYMBOL]: Flags, coats of arms, official uniforms, banknotes/coins.
```

### **2. Training Dataset Format (Example JSON-L for Fine-Tuning)**

The model is trained on pairs of **Input (Script/Instruction) →
Output (Structured IP JSON Matrix)**.

#### **Example Training Prompt:**

> **Input:** *"EXT. BUENOS AIRES STREET – NIGHT. LUCAS (30) walks
> wearing Sony headphones, listening to 'Bioluminescence' by a local
> artist. He enters a Starbucks while watching a Champions League
> match streaming on his iPhone. At the table, the CONCEPT ARTIST
> shows him the original alien design (Attached: alien_v1.png)."*

#### **Expected Output JSON (Model Training):**

```json
{
  "project_analysis": {
    "detected_events": [
      {
        "id": "EVT-001",
        "raw_text": "Sony headphones / iPhone",
        "category": "1. INDUSTRIAL PROPERTY",
        "tag": "BRAND",
        "risk_level": "Medium",
        "legal_requirement": "Brand Clearance / Product Placement Approval",
        "action_required": "Request authorization from Sony and Apple or apply visual greeking."
      },
      {
        "id": "EVT-002",
        "raw_text": "'Bioluminescence' by a local artist",
        "category": "2. INTELLECTUAL PROPERTY - MUSIC",
        "tag": "MUSIC_EXISTING",
        "risk_level": "High",
        "legal_requirement": "Sync License + Master License",
        "action_required": "Contact the composer/independent label for a synchronization agreement."
      },
      {
        "id": "EVT-003",
        "raw_text": "Enters a Starbucks",
        "category": "5. LOCATIONS",
        "tag": "LOCATION_PRIV",
        "risk_level": "High",
        "legal_requirement": "Location Release Form",
        "action_required": "Sign a filming permit with the company or the commercial venue's administrator."
      },
      {
        "id": "EVT-004",
        "raw_text": "Champions League match streaming",
        "category": "2. INTELLECTUAL PROPERTY - AUDIOVISUAL",
        "tag": "MEDIA_AV",
        "risk_level": "Critical",
        "legal_requirement": "Broadcasting Clip Rights",
        "action_required": "Obtain licenses from UEFA/the broadcasting network or replace with original footage."
      },
      {
        "id": "EVT-005",
        "raw_text": "original alien design (Attached: alien_v1.png)",
        "category": "4. INTEGRATED VISUAL WORKS",
        "tag": "PROPS_DESIGN",
        "risk_level": "High",
        "legal_requirement": "Work for Hire / Concept Art Rights Assignment",
        "action_required": "Have the illustrator sign the Full Assignment of Economic Rights."
      }
    ]
  }
}
```

### **3. Multimodal Pipeline for Attached Files**

The model will not only read the script text but will also connect
three specialized sub-models:

1.  **Primary LLM (Legal-Tech Core):**

    - Converts plain text (PDF, Fountain, Final Draft) into events
      classified according to the 6-rights taxonomy.

2.  **Computer Vision (CV Engine):**

    - Processes image attachments (wardrobe, storyboards, location
      photos) through a **Vector Index Search** against public patent
      and design registries (WIPO, USPTO) to issue a brand/work
      visual-similarity alert.

3.  **Audio Analysis Module (Fingerprinting):**

    - Analyzes uploaded demos or test audio to classify whether it
      matches phonograms in commercial databases (via audio ID) or
      whether it is a clean work for original assignment.

////////////////////////////////////////////////////////////////////////////////////////////////////////////////

**Territorial Actionability Engine (Country Orchestrator)**

## **1. Global Logic: How the AI Proceeds Based on the Detected Right**

When the AI extracts an event from the script, it applies a
structured decision-tree algorithm:

[Input: Text / File]

│

▼

[Event Classification] ──► IP Category (Music, Brand, Image, etc.)

│

▼

[Ownership Matrix] ─────► Is It Original / Work for Hire? OR Is It Third-Party?

│

├─────────────────────────────────┐

▼ ▼

[Route A: Original Work] [Route B: Third-Party Work]

1. Work Deposit 1. Identify Rights Holder / Representative

2. Assignment Agreement 2. Draft Outreach (Request Email)

3. Trademark/Design Registration 3. Manage License (Sync, Brand Clearance, etc.)

│ │

└─────────────────────────────────┘

│

▼

[Output to Compliance Tracker]

(Progress Percentage + Traffic-Light Status)

## **2. Extended Territorial Framework: Bodies, Laws, and Actionability Workflows (10 Countries)**

Below is a detailed description of how the AI processes each of the
10 defined jurisdictions according to the institutional map, local
laws, Collective Management Societies (CMS), and outreach workflows:

### **1. ARGENTINA 🇦🇷**

**Key Regulatory Framework**

- **Law No. 11,723** (Legal Framework for Intellectual Property).

- **Law No. 22,362** (Trademarks and Designations).

- **National Civil and Commercial Code (Art. 53):** Right to image
  and voice.

**Official Registration and Deposit Bodies**

- **DNDA (National Copyright Directorate):** Registration of
  unpublished/published scripts, musical works, and audiovisual
  production contracts.

  - *Access:* Remote Procedures Portal (TAD) / info_dnda@jus.gov.ar.

- **INPI (National Institute of Industrial Property):** Registration
  of trademarks for the film/series, characters, or merchandising
  elements.

  - *Access:* INPI Procedures Portal (using AFIP tax ID / Clave
    Fiscal).

**Collective Management Societies (CMS) and Actors**

- **SADAIC (Music – Composers/Publishers):** Synchronization and
  public performance licenses.

  - *Contact:* sadaic.org.ar | Synchronization Department.

- **AADI-CAPIF (Music – Performers and Phonogram Producers):**
  Settlement of phonogram rights.

  - *ISRC Management:* CAPIF issues the recording identification code
    (isrc@capif.org.ar).

- **SAGAI (Argentine Society for the Management of Performing
  Actors):** Management of actors' image/performance rights.

  - *Contact:* sagai.org.ar.

- **AAA (Argentine Actors Association):** Approval of talent
  contracts and image releases.

- **DAC (Argentine Film Directors):** Management of audiovisual
  directors' copyright.

### **2. UNITED STATES 🇺🇸**

**Key Regulatory Framework**

- **U.S. Code Title 17 (Copyright Law):** *Fair Use* doctrine
  (Section 107) and *Work Made for Hire* (Section 101).

- **Lanham Act (Trademark Law):** Registration and commercial
  protection of trademarks.

- **Right of Publicity (State laws, e.g., California Civil Code §
  3344):** Commercial use of name, voice, and likeness.

**Official Registration and Deposit Bodies**

- **U.S. Copyright Office (USCO):** Official registration of scripts,
  compositions, and completed audiovisual works.

  - *Access:* copyright.gov (eCO System).

- **USPTO (United States Patent and Trademark Office):** Registration
  of trademarks, titles, and franchise logos.

  - *Access:* uspto.gov.

**Collective Management Societies (CMS) and Guilds**

- **Music (Publishing & Performance):** ASCAP, BMI, SESAC. (Unified
  search via the *Songview* database to locate publishers).

- **Music (Master Licensing):** SoundExchange (digital phonogram
  rights) and *Major* labels (Universal, Sony, Warner).

- **SAG-AFTRA:** Actors' union (validation of *Talent Release Forms*
  under union agreements).

- **WGA / DGA (Writers/Directors Guild of America):** Regulation of
  the *Chain of Title* for writers and directors.

### **3. SPAIN / EUROPEAN UNION 🇪🇸 🇪🇺**

**Key Regulatory Framework**

- **Royal Legislative Decree 1/1996:** Spain's Intellectual Property
  Law.

- **Directive (EU) 2019/790:** Digital Single Market and content
  licensing.

- **Organic Law 1/1982:** Civil protection of the right to honor,
  privacy, and one's own image.

**Official Registration and Deposit Bodies**

- **Intellectual Property Registry (Ministry of Culture):** Formal
  registration of scripts and productions.

  - *Access:* Spain's Ministry of Culture Portal.

- **OEPM / EUIPO:** National trademark registration (oepm.es) and
  EU-wide registration (euipo.europa.eu).

**Collective Management Societies (CMS) and Entities**

- **SGAE:** Music synchronization authorizations and
  audiovisual/dramatic repertoire.

- **DAMA (Audiovisual Media Copyright):** Specialized management for
  screenwriters and directors.

- **AIE:** Society of Music Performing Artists.

- **EGEDA:** Management of audiovisual producers' rights (private
  copying and retransmission).

- **AISGE:** Management of image and performance rights for actors
  and voice actors.

### **4. MEXICO 🇲🇽**

**Key Regulatory Framework**

- **Federal Copyright Law (LFDA):** Protection of cinematographic
  works and reservation of rights.

- **Federal Law for the Protection of Industrial Property (LFPPI):**
  Regulatory framework for trademarks and commercial notices.

**Official Registration and Deposit Bodies**

- **INDAUTOR (National Copyright Institute):** Registration of
  literary works/scripts and *Reservations of Rights for Exclusive
  Use* (titles and characters).

  - *Access:* indautor.gob.mx.

- **IMPI (Mexican Institute of Industrial Property):** Registration
  of trademarks associated with the project.

  - *Access:* gob.mx/impi.

**Collective Management Societies (CMS) and Unions**

- **SACM (Mexican Society of Authors and Composers):**
  Synchronization and music performance licenses.

- **ANDI (National Association of Performers):** Image and
  performance rights for on-screen actors.

- **SOMEREC:** Phonogram licenses (master rights).

- **STPC / ANDA:** Film Production Workers' Union and National Actors
  Association (contract approval).

### **5. CANADA 🇨🇦**

**Key Regulatory Framework**

- **Copyright Act (R.S.C., 1985, c. C-42):** Governs copyright and
  inalienable moral rights.

- **Trademarks Act (R.S.C., 1985, c. T-13):** Protection of
  trademarks and industrial property.

**Official Registration and Deposit Bodies**

- **CIPO (Canadian Intellectual Property Office):** Official deposit
  and registration of Copyright and Trademarks.

  - *Access:* ic.gc.ca/cipo.

**Collective Management Societies (CMS) and Unions**

- **SOCAN (Society of Composers, Authors and Music Publishers of
  Canada):** Management of music licenses.

- **ACTRA (Alliance of Canadian Cinema, Television and Radio
  Artists):** Union regulating the use of talent image and rates.

- **CMPA (Canadian Media Producers Association):** Standardization of
  chain-of-title contracts for local and international productions.

### **6. FRANCE 🇫🇷**

**Key Regulatory Framework**

- **Code de la Propriété Intellectuelle (CPI):** Strict emphasis on
  the creator's inalienable and imprescriptible Moral Rights.

- **Loi n° 78-17 (Informatique et Libertés):** Protection of personal
  data and image.

**Official Registration and Deposit Bodies**

- **CNC (Centre National du Cinéma et de l'image animée):** Registre
  Public de l'Audiovisuel (RPA) for recording production contracts and
  chain of title.

- **INPI (Institut National de la Propriété Industrielle):**
  Registration of trademarks and industrial designs (inpi.fr).

**Collective Management Societies (CMS)**

- **SACEM (Société des Auteurs, Compositeurs et Éditeurs de
  Musique):** Music synchronization licenses.

- **SACD (Société des Auteurs et Compositeurs Dramatiques):**
  Management of authorship for scripts, direction, and dramatic
  texts.

- **ADAMI / SPEDIDAM:** Management of related rights for actors,
  performers, and performing musicians.

- **PROCIREP:** Entity protecting the rights of film and audiovisual
  producers.

### **7. UNITED KINGDOM 🇬🇧**

**Key Regulatory Framework**

- **Copyright, Designs and Patents Act 1988 (CDPA):** Legal framework
  for copyright, *Design Rights*, and exceptions.

- **Trade Marks Act 1994:** Trademark law.

**Official Registration and Deposit Bodies**

- **UK IPO (Intellectual Property Office):** Formal registration of
  Trademarks and Designs (gov.uk/ipo). *Note: The UK has no state
  copyright registry; the right arises upon creation, requiring
  evidence of private deposit.*

**Collective Management Societies (CMS) and Unions**

- **PRS for Music / MCPS (Mechanical-Copyright Protection Society):**
  Mechanical and music synchronization licenses.

- **PPL (Phonographic Performance Limited):** Licensing of audio
  recordings (master).

- **Equity UK:** Actors' union for signing *Talent Release
  Agreements* and image agreements.

### **8. INDIA 🇮🇳**

**Key Regulatory Framework**

- **The Copyright Act, 1957 (2012 Amendments):** Governs the rights
  of composers, screenwriters, and producers.

- **The Trade Marks Act, 1999:** Protection of trade names and
  titles.

**Official Registration and Deposit Bodies**

- **Copyright Office India:** National registration of scripts and
  cinematographic works (copyright.gov.in).

- **CGPDTM (IP India):** Registration of trademarks and industrial
  property (ipindia.gov.in).

**Collective Management Societies (CMS) and Associations**

- **IPRS (Indian Performing Right Society):** Administration of music
  rights and compositions.

- **PPL India:** Licenses for phonogram producers.

- **CINTAA (Cine and TV Artistes' Association):** Regulation of
  contracts and image releases for talent and performers.

### **9. BRAZIL 🇧🇷**

**Key Regulatory Framework**

- **Lei de Direitos Autorais (Law No. 9,610/98):** Governs copyright
  and related rights.

- **Lei de Propriedade Industrial (Law No. 9,279/96):** Trademarks
  and advertising expressions.

**Official Registration and Deposit Bodies**

- **EDA (Copyright Office – National Library):** Official
  registration of unpublished scripts and stories (bn.gov.br).

- **INPI Brazil:** Registration of trademarks for audiovisual
  projects (gov.br/inpi).

**Collective Management Societies (CMS) and Unions**

- **ECAD (Central Office for Collection and Distribution):** Unified
  body for collecting music rights.

- **ABRAMUS / UBC:** Music authors' societies affiliated with ECAD
  for synchronization licenses.

- **SATED:** Union of Entertainment Artists and Technicians (image
  releases and state-level labor agreements).

### **10. SOUTH KOREA 🇰🇷**

**Key Regulatory Framework**

- **Copyright Act of Korea (Act No. 14083):** Governs the protection
  of audiovisual and musical works and *Webtoons*.

- **Trademark Act:** Protection of distinctive signs and trademarks.

**Official Registration and Deposit Bodies**

- **KCC (Korea Copyright Commission):** Official registration of
  scripts and audiovisual works (copyright.or.kr).

- **KIPO (Korean Intellectual Property Office):** Registration of
  trademarks and merchandising (kipo.go.kr).

**Collective Management Societies (CMS) and Associations**

- **KOMCA (Korea Music Copyright Association):** Licensing of musical
  compositions.

- **FKMP (Federation of Korean Music Performers):** Management of
  performers' rights.

- **KAA (Korean Actors Association):** Regulation of image and voice
  rights releases in independent productions.

This structured matrix is the engine the AI will query to generate
the **Compliance Tracker**, automatically adapting recommendations and
outreach drafts according to the selected territory.

## **3. Rights-Holder Lookup Logic and Outreach Generation**

When the AI detects a protected third-party work (e.g., a song or a
trademark), it executes the following three phases:

### **Phase 1: Trace the Rights Holder (*Rights Holder Lookup*)**

- **For Music:** The AI queries the public APIs of the relevant
  entities (ASCAP/BMI Songview in the US, SADAIC in Argentina, the
  ISWC Network) to identify the *Music Publisher* and the *Record
  Label* (master owner).

- **For Trademarks:** The AI queries global trademark databases (WIPO
  Global Brand Database, TMView) to locate the official company name
  and the registered legal representative.

### **Phase 2: Automatic Drafting of Communications (*Outreach Templates*)**

The AI automatically generates a personalized email draft based on
the case.

```
SUBJECT: Music Synchronization License Request – Audiovisual Production "[Project Name]"

Dear [Publisher Name / Label / Legal Contact]:

We are writing on behalf of [Production Company Name] regarding the audiovisual project titled "[Project Name]", directed by [Director Name].

We would like to request use authorization / a Synchronization License for the musical work described below:

- Title of the work: [Song Name]
- Author/Composer: [Name]
- Intended use: [Scene description – e.g., background music on the radio, 15-second duration]
- Territory: [Worldwide / Regional]
- Media: [Film, Streaming, TV, Festivals]

We would appreciate it if you could indicate the formal procedure and the fees/quote for issuing the corresponding license.

Sincerely,

[Producer Name / Legal Department]
```

### **Phase 3: Assignment to the Compliance Tracker (Dashboard)**

The event is recorded in the platform's database with status **In
Progress (🟡)** until the user attaches the signed contract or proof
of payment, at which point the AI validates the document and the
tracker changes to **Completed (🟢 100%)**.
