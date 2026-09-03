"""What to ask the legal corpus about a finding.

Extracted because both pipeline use cases need it and `evaluate_delta.py` had
built its own copy inline, which meant fixing one left the other still broken.
AGENT.md section 4 allows an abstraction on the third occurrence; this is the
second, and the duplicate was already carrying a defect rather than merely
repeating itself.

**Terms, not a sentence.** The data store matches terms. Probed against the
real corpus on 2026-09-03: `trademark marca registrada` retrieves both
Argentine statutes, while `INDUSTRIAL_PROPERTY clearance: a Ferrari Testarossa`
retrieves nothing. Every word of that old shape was unfindable -- no statute
contains an enum name, the word "clearance", or a car model.

**Bilingual on purpose.** Each jurisdiction's corpus is in its own language and
the pipeline speaks English, so a query in one language alone reaches half the
corpus at best.

**No asset name.** SDD section 4.1 step 5 asks what the law says about "this
category of use", and the asset is what `RightsResearch` looks up, not what a
statute is about. Including it also measurably hurts: adding "Quilmes" to a
query that returned two documents dropped it to one.

**These terms are measured, not reasoned, and they are not stable.** Each was
checked against the live corpus, and the three with law behind them retrieve
four, four and three citations respectively. But the grounded path runs through
a model that decides whether to retrieve at all, so which phrasing wins moves
between runs: one probe had `trademark marca registrada` returning four and
`derecho de autor obra musical` returning none, and the next had it the other
way round. Tuning these strings further is chasing noise. **The real lever is
corpus size** -- six of the eight categories have no Argentine law loaded at
all, so no phrasing can ground them.
"""

from clearcut.domain.finding import Category, Finding

_GROUNDING_TERMS: dict[Category, str] = {
    Category.INDUSTRIAL_PROPERTY: "trademark marca registrada",
    Category.COPYRIGHT_WORKS: "derecho de autor obra musical",
    Category.PERSONALITY_IMAGE: "personality rights nombre seudonimo retrato",
    Category.INTEGRATED_VISUAL: "artistic work design obra artistica dibujo",
    Category.LOCATIONS_PERMITS: "filming permit location permiso rodaje",
    Category.SPECIAL_SYMBOLS: "official symbols emblema bandera escudo",
}


def grounding_query(finding: Finding) -> str:
    """The legal subject of the finding's category.

    CONTINUITY and POLICY never reach here: both use cases skip the grounding
    lookup for them, because a project-bible contradiction is not a question
    about statute.
    """
    return _GROUNDING_TERMS[finding.category]
