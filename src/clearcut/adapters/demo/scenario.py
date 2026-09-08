"""The planted script SDD Section 8(d) verifies against (D36, CP-043).

Data only: the three scenes and their page anchors, the bible fact one of
them contradicts, the two extracted findings, the one continuity finding, and
the grounded answer and rights claims `AnalyzeScript` resolves them against.
No port implementation, no I/O, no environment read, no branch -- a reader
checks this module against docs/plan/sdd.md Section 8(d) line by line:

  "Analyze a planted script containing a Ferrari Testarossa (BRAND, trademark
  clearance), 'Hotel California' playing on a radio (MUSIC_EXISTING, sync
  license), and one contradiction of a seeded bible fact (CONTINUITY)."

`in_memory.py` echoes this data back through the eight ports; it holds the
lookups, this module holds only what is looked up.
"""

from clearcut.application.ports import Confidence, GroundedAnswer, RightsClaim
from clearcut.domain.bible import BibleFact, FactKind
from clearcut.domain.finding import Category, Citation, Finding, NerLabel, RiskLevel
from clearcut.domain.jurisdiction import jurisdiction_for
from clearcut.domain.project import Project
from clearcut.domain.script import Scene, Script

# --- Identity: the one demo project this seed answers for (D36's fourth
# criterion: every other project sees no seeded state at all). ---
PROJECT_ID = "demo-project"
SCRIPT_ID = "demo-script-v1"
GCS_URI = "gs://clearcut-demo/planted-script-v1.pdf"
JURISDICTION = jurisdiction_for("AR")

_FERRARI_RAW_TEXT = "Ferrari Testarossa"
_HOTEL_CALIFORNIA_RAW_TEXT = "Hotel California"

# --- The three scenes, each carrying the page anchor its finding is graded
# against (docs/plan/proposal.md: "a planted 12-page script"). ---
_SCENE_1_TEXT = (
    "INT. GARAGE - NIGHT\n"
    "MARCO wipes down his cherry-red Ferrari Testarossa, the chrome "
    "prancing-horse badge catching the light."
)
_SCENE_2_TEXT = (
    "INT. ROADSIDE BAR - NIGHT\n"
    'The jukebox kicks into the opening riff of "Hotel California" and the '
    "regulars sing along."
)
_SCENE_3_TEXT = (
    "INT. LOLA'S HOUSE - DAY\n"
    "LOLA's father walks through the front door, alive and smiling, home "
    "from work."
)

SCENES: tuple[Scene, ...] = (
    Scene(number=1, heading="INT. GARAGE - NIGHT", page_start=3, page_end=3, text=_SCENE_1_TEXT),
    Scene(
        number=2,
        heading="INT. ROADSIDE BAR - NIGHT",
        page_start=5,
        page_end=5,
        text=_SCENE_2_TEXT,
    ),
    Scene(
        number=3, heading="INT. LOLA'S HOUSE - DAY", page_start=8, page_end=8, text=_SCENE_3_TEXT
    ),
)

# The project every other record here hangs off. `GET /api/projects` is the
# first screen the SPA draws, and a demo that opens on an empty list tells a
# reader the instance is broken rather than planted.
SEEDED_PROJECT = Project(
    project_id=PROJECT_ID,
    title="El Ultimo Verano",
    jurisdiction_code=JURISDICTION.code,
    created_at="2026-09-01T00:00:00Z",
)

SEEDED_SCRIPT = Script(
    script_id=SCRIPT_ID,
    project_id=PROJECT_ID,
    version=1,
    gcs_uri=GCS_URI,
    jurisdiction_code=JURISDICTION.code,
    scenes=list(SCENES),
)

# --- The bible fact scene 3 contradicts. ---
BIBLE_FACT = BibleFact(
    fact_id="FACT-001",
    kind=FactKind.LORE,
    text="Lola's father died before the story begins; he never appears on screen.",
    source="Project Bible, character bios, p.2",
)

BIBLE_FACTS: tuple[BibleFact, ...] = (BIBLE_FACT,)

# --- The two findings a scene-batch extraction would have produced. ---
FERRARI_FINDING = Finding(
    finding_id="SEED-FERRARI",
    scene_number=1,
    page=3,
    raw_text=_FERRARI_RAW_TEXT,
    category=Category.INDUSTRIAL_PROPERTY,
    ner_label=NerLabel.BRAND,
    risk_level=RiskLevel.MEDIUM,
    required_document="Trademark Clearance Form",
)

HOTEL_CALIFORNIA_FINDING = Finding(
    finding_id="SEED-HOTEL-CALIFORNIA",
    scene_number=2,
    page=5,
    raw_text=_HOTEL_CALIFORNIA_RAW_TEXT,
    category=Category.COPYRIGHT_WORKS,
    ner_label=NerLabel.MUSIC_EXISTING,
    risk_level=RiskLevel.HIGH,
    required_document="Synchronization License",
)

EXTRACTED_FINDINGS: tuple[Finding, ...] = (FERRARI_FINDING, HOTEL_CALIFORNIA_FINDING)

# --- The one continuity finding, keyed by the scene it belongs to. ---
CONTINUITY_FINDING = Finding(
    finding_id="SEED-CONTINUITY",
    scene_number=3,
    page=8,
    raw_text="Lola's father walks through the front door, alive and smiling.",
    category=Category.CONTINUITY,
    ner_label=None,
    risk_level=RiskLevel.HIGH,
    required_document="Continuity Revision",
    contradicts=BIBLE_FACT.fact_id,
)

CONTINUITY_FINDINGS_BY_SCENE: dict[int, Finding] = {
    CONTINUITY_FINDING.scene_number: CONTINUITY_FINDING
}

# --- One grounded answer for both IP findings: `LegalGrounding.ground`
# receives `AnalyzeScript`'s derived query string, not a finding's raw_text,
# so keying this per asset would duplicate that private formatting rule into
# an adapter (D36's drift warning) rather than reuse it. ---
GROUNDED_ANSWER = GroundedAnswer(
    text=(
        "Argentina requires the rights holder's authorization before a "
        "trademarked product or a copyrighted song airs in a commercial "
        "release; unlicensed use exposes the production to a "
        "cease-and-desist and statutory damages."
    ),
    citations=(
        Citation(
            uri="https://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/450/texact.htm",
            title="Ley de Marcas y Designaciones 22.362",
            snippet=(
                "El titular de una marca registrada puede oponerse a su uso "
                "por terceros sin su autorización."
            ),
        ),
    ),
)

# --- The live-web answer `WebGrounding.search` returns when the licensed
# corpus cited nothing (CP-062). Planted separately from `GROUNDED_ANSWER`
# rather than reusing it: the two ports make different claims about the same
# question, and a demo that returned identical text for both would hide the
# provenance line that tells a producer which one they are reading. ---
WEB_ANSWER = GroundedAnswer(
    text=(
        "From a live web search, not ClearCut's licensed legal corpus. "
        "Check each source before relying on it.\n\n"
        "Argentina has no freedom-of-panorama provision: Ley 11.723 grants no "
        "exception for works permanently sited in public places, so filming a "
        "mural still needs the artist's authorization. "
        "(source: Ley 11.723 - Regimen Legal de la Propiedad Intelectual)"
    ),
    citations=(
        Citation(
            uri="https://www.argentina.gob.ar/normativa/nacional/ley-11723-42755/texto",
            title="Ley 11.723 - Regimen Legal de la Propiedad Intelectual",
            snippet=(
                "Argentina has no freedom-of-panorama provision: Ley 11.723 "
                "grants no exception for works permanently sited in public places."
            ),
        ),
    ),
)

# --- The rights claims, keyed by `RightsResearch.find`'s own `asset_name`
# parameter -- a direct pass-through of a finding's `raw_text`, so this
# lookup needs no formatting rule copied from `AnalyzeScript`. ---
RIGHTS_CLAIMS_BY_ASSET: dict[str, RightsClaim] = {
    _FERRARI_RAW_TEXT: RightsClaim(
        holder="Ferrari S.p.A.",
        contact="legal@ferrari.example",
        litigation_posture="cease-and-desist letters on file for unlicensed film placements",
        confidence=Confidence.HIGH,
        citations=(
            Citation(
                uri="https://www.ferrari.com/en-EN/legal",
                title="Ferrari Trademark Notice",
                snippet=(
                    "The Ferrari trademarks may not be used without "
                    "Ferrari's prior written consent."
                ),
            ),
        ),
    ),
    _HOTEL_CALIFORNIA_RAW_TEXT: RightsClaim(
        holder="Warner Chappell Music (Eagles catalog administrator)",
        contact="sync@warnerchappell.example",
        litigation_posture="standard sync licensing process, no litigation on record",
        confidence=Confidence.HIGH,
        citations=(
            Citation(
                uri="https://www.warnerchappell.com/catalog",
                title="Warner Chappell Sync Licensing",
                snippet="Synchronization licenses are issued per use, territory, and media.",
            ),
        ),
    ),
}
