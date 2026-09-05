import { describe, expect, it } from "vitest";

import type { TrackerItem } from "../api/client";
import { CAPTURED_ANALYSIS, SCRIPT_FIXTURE, TRACKER_FIXTURE } from "./index";

/**
 * Both files are the bodies the mock server returned, captured in-process
 * from `clearcut.composition.create_app()` (D60): the POST that planted the
 * demo script, then the GET that listed its tracker. They are the wire, not
 * a hand-written approximation of it, which is why every row starts BLOCKED
 * and the continuity item carries empty strings.
 *
 * The casts in `index.ts` are the acceptance criterion, not the assertions
 * below them: they type-check the fixture JSON against the exact shapes
 * `client.ts` declares. `as`, not `:`, on purpose -- `resolveJsonModule`
 * widens every JSON string literal to `string`, so a direct `:` annotation
 * never structurally matches a field typed as a literal union (RiskLevel,
 * Category, TrackerState, ...) even when the fixture is correct. `as` only
 * requires the two shapes to "sufficiently overlap": a renamed field breaks
 * the overlap in both directions and stops compiling, but a field that
 * merely goes missing from one side does not, because the wider shape still
 * accepts the narrower one. The key pins below exist to close that gap.
 */

// Compile-visible pin (CP-053): the server emits `contact`,
// `litigation_posture` and `note` as bare strings -- `""` when absent,
// never `null` and never an object (`_tracker_item_json`,
// adapters/http/routes.py; `TrackerItem`, domain/tracker.py). If any of
// these three fields ever regresses to an optional or object type, this
// block stops compiling.
const contact: string = TRACKER_FIXTURE[0].contact;
const litigationPosture: string = TRACKER_FIXTURE[0].litigation_posture;
const note: string = TRACKER_FIXTURE[2].note;
void contact;
void litigationPosture;
void note;

// Compile-visible pin (CP-053 review attempt 1, finding 1): `project_id` is
// that checkpoint's headline addition to `TrackerItem`. The `as` cast lets
// a field go missing silently, so this line stops compiling if
// `project_id` is removed from `TrackerItem`.
const projectId: string = TRACKER_FIXTURE[0].project_id;
void projectId;

// Compile-visible pin (CP-053 review attempt 1, finding 2): the key test
// below asserts `Object.keys(...)` against a hardcoded list, which pins the
// *fixture*, never the *interface* -- deleting `gcs_uri` from `Script`
// leaves that assertion, typecheck and all tests green. This line stops
// compiling if `gcs_uri` is removed from `Script`.
const gcsUri: string = SCRIPT_FIXTURE.gcs_uri;
void gcsUri;

// The capture's own tracker rows, pinned to the declared element type.
const items: TrackerItem[] = CAPTURED_ANALYSIS.tracker_items;
void items;

/** Every key `_tracker_item_json` writes, and nothing else (D58). */
const TRACKER_ITEM_KEYS = [
  "item_id",
  "project_id",
  "finding_id",
  "scene_numbers",
  "state",
  "needs_review",
  "required_document",
  "contact",
  "litigation_posture",
  "draft_email",
  "note",
  "updated_at",
  "version",
];

describe("captured analysis", () => {
  it("carries at least one scene and one finding", () => {
    expect(CAPTURED_ANALYSIS.scenes.length).toBeGreaterThan(0);
    expect(CAPTURED_ANALYSIS.findings.length).toBeGreaterThan(0);
  });

  it("still carries the eight keys the pre-contract wire had, tracker_items included", () => {
    expect(Object.keys(CAPTURED_ANALYSIS).sort()).toEqual(
      [
        "script_id",
        "project_id",
        "version",
        "gcs_uri",
        "jurisdiction_code",
        "scenes",
        "findings",
        "tracker_items",
      ].sort(),
    );
    expect(CAPTURED_ANALYSIS.tracker_items.length).toBeGreaterThan(0);
  });

  it("is the planted scenario: three scenes with text and three EVT findings", () => {
    expect(CAPTURED_ANALYSIS.scenes.map((scene) => scene.number)).toEqual([1, 2, 3]);
    expect(CAPTURED_ANALYSIS.scenes.every((scene) => scene.text.length > 0)).toBe(true);
    expect(CAPTURED_ANALYSIS.findings.map((finding) => finding.finding_id)).toEqual([
      "EVT-001",
      "EVT-002",
      "EVT-003",
    ]);
  });

  it("carries the continuity finding with its contradicted fact and no citations", () => {
    const continuity = CAPTURED_ANALYSIS.findings[2];

    expect(continuity.category).toBe("CONTINUITY");
    expect(continuity.contradicts).toBe("FACT-001");
    expect(continuity.citations).toEqual([]);
  });
});

describe("script fixture", () => {
  it("carries the seven keys a Script has, and never the wire's tracker_items", () => {
    expect(Object.keys(SCRIPT_FIXTURE).sort()).toEqual(
      [
        "script_id",
        "project_id",
        "version",
        "gcs_uri",
        "jurisdiction_code",
        "scenes",
        "findings",
      ].sort(),
    );
  });

  it("gives every scene an empty spans array rather than an invented offset", () => {
    expect(SCRIPT_FIXTURE.scenes.every((scene) => scene.spans.length === 0)).toBe(true);
  });

  it("keeps the capture's scenes and findings unchanged apart from spans", () => {
    expect(SCRIPT_FIXTURE.findings).toEqual(CAPTURED_ANALYSIS.findings);
    expect(SCRIPT_FIXTURE.scenes.map((scene) => scene.heading)).toEqual(
      CAPTURED_ANALYSIS.scenes.map((scene) => scene.heading),
    );
  });
});

describe("tracker fixture", () => {
  it("starts every row BLOCKED, as the server does right after an analysis", () => {
    expect(TRACKER_FIXTURE.map((item) => item.state)).toEqual([
      "BLOCKED",
      "BLOCKED",
      "BLOCKED",
    ]);
  });

  it("carries exactly the thirteen TrackerItem keys on every row", () => {
    for (const item of TRACKER_FIXTURE) {
      expect(Object.keys(item).sort()).toEqual([...TRACKER_ITEM_KEYS].sort());
    }
  });

  it("carries the scenario's real contact strings, empty string when absent", () => {
    const contacts = TRACKER_FIXTURE.map((item) => item.contact);

    expect(contacts).toEqual([
      "legal@ferrari.example",
      "sync@warnerchappell.example",
      "",
    ]);
  });

  it("lists the same items the captured analysis carried", () => {
    expect(TRACKER_FIXTURE.map((item) => item.item_id)).toEqual(
      CAPTURED_ANALYSIS.tracker_items.map((item) => item.item_id),
    );
  });
});
