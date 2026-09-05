# ADR 0015: Highlight spans are computed in the domain, not searched for in the browser

Status: Accepted
Date: 2026-09-05

## Context

The Script Review screen renders the screenplay as numbered lines with the
flagged text highlighted inline, the way a proofreader marks prose. Clicking a
highlight selects that finding. This is the product's central screen and the one
thing no competitor's spreadsheet does.

To draw it, something has to know where in the scene text each finding's
`raw_text` begins and ends. `Finding` carries `raw_text`, `scene_number` and
`page`. It carries no character offsets, and the model is not asked for any.

Asking Gemini for offsets is the obvious move and the wrong one. Offsets are
arithmetic over a string the model reproduces rather than measures, and a model
that miscounts by three characters produces a highlight that straddles a word
boundary with no signal that anything went wrong. The extractor already declines
to trust the model on `category`, re-deriving it from `ner_label` through
`taxonomy.category_for`. The same reasoning applies here, more strongly:
a wrong category is visibly wrong, a wrong offset is silently wrong.

The alternative is to search for `raw_text` inside `Scene.text`. The question is
where that search runs.

## Decision

A pure function in the domain: `domain/highlight.py::spans_for(scene, findings)`
returns the ordered, non-overlapping spans for one scene, each carrying its
`start`, `end`, `finding_id` and risk. The script read endpoint serves them. The
browser renders spans it is given and never searches.

Matching normalizes through `domain.script.normalize_text`, the same primitive
`dedupe.py` already uses to decide two findings name the same asset. One
normalization rule, one place, already tested.

Three rules the function owns, because they are decisions rather than rendering:

- A `raw_text` that appears more than once in a scene highlights **every**
  occurrence. Coca-Cola named three times is flagged three times; picking the
  first would silently hide two.
- Overlapping spans resolve to the higher-risk finding. Two findings claiming
  the same characters is a real outcome of deduplication across categories, and
  the reader needs one colour, not a nested tag.
- A `raw_text` the scene does not contain yields no span, and that is not an
  error. The model paraphrased, or the scene changed between versions. The
  finding still appears in the suggestions rail with its scene and page; only
  the inline mark is absent.

This lives in the domain rather than the application layer because it is a rule
about what a script and its findings mean, expressed in domain types, with no
I/O. It lives on the server rather than in the browser for three reasons: an
export or a PDF report needs the same spans and would otherwise reimplement the
matcher; the three rules above are testable in the tier that already forbids
mocking; and the browser is the wrong place to decide which of two findings wins
a character range.

## Consequences

The web client has no matching algorithm, no tokenizer and no normalization
rule to keep in step with Python. It maps a `spans` array to `<span>` elements,
which is view work.

The three rules get unit tests against the real domain types instead of jsdom
assertions about rendered markup.

Spans are computed on read rather than stored. That is a loop over the findings
of one scene against one string, which is nothing next to the twenty-minute
analysis that produced them. If a script ever grows large enough for it to
matter, the spans can be persisted alongside the findings without changing the
wire shape.

A paraphrasing model produces findings with no inline mark, and the screen looks
less complete than the item count promises. Surfacing that honestly -- the
suggestion is listed, the highlight is absent -- is better than inventing a
position, and it makes prompt regressions visible rather than silent.
