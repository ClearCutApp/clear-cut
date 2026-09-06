import type { Script, Span } from "../api/client";
import { SCRIPT_FIXTURE } from "./index";

/**
 * The captured analysis with the span offsets a live server computes for
 * it, so a test can render the notepad the way a reader meets it.
 *
 * `analyze.json` was captured before the contract grew `spans`, and its
 * bytes stay exactly as the server sent them (see `index.ts`). The offsets
 * below are the ones a live read returns for that same text. They are
 * written as numbers rather than searched for at import time: the browser
 * never searches a scene for a phrase (ADR 0015), and neither should the
 * fixture that stands in for the server.
 *
 * Two of the three findings get a span. The third is the case worth
 * keeping a fixture for: the scene reads "LOLA's father walks through the
 * front door, alive and smiling, home from work." and the analysis
 * reported "Lola's father walks through the front door, alive and
 * smiling." -- a paraphrase, not a stretch of the text. No position exists
 * for it, so the screen lists it and marks it nowhere.
 */
const SPANS: Span[] = [
  { scene_number: 1, start: 52, end: 70, finding_id: "EVT-001", risk: "MEDIUM" },
  { scene_number: 2, start: 70, end: 86, finding_id: "EVT-002", risk: "HIGH" },
];

export const SPANNED_SCRIPT_FIXTURE: Script = {
  ...SCRIPT_FIXTURE,
  scenes: SCRIPT_FIXTURE.scenes.map((scene) => ({
    ...scene,
    spans: SPANS.filter((span) => span.scene_number === scene.number),
  })),
};
