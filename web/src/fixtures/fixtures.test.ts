import { describe, expect, it } from "vitest";

import type {
  AnalyzeResponse,
  TrackerItem,
  TrackerResponse,
} from "../api/client";
import analyzeData from "./analyze.json";
import trackerData from "./tracker.json";

/**
 * These two casts are the acceptance criterion, not the assertions below
 * them: they type-check the fixture JSON against the exact response shapes
 * `client.ts` declares. `as`, not `:`, on purpose — `resolveJsonModule`
 * widens every JSON string literal to `string`, so a direct `:` annotation
 * never structurally matches a field typed as a literal union (RiskLevel,
 * Category, TrackerState, ...) even when the fixture is correct. `as` still
 * requires the two shapes to "sufficiently overlap", which does catch a
 * renamed or missing field at any depth — verified directly against this
 * project's own tsc (see this checkpoint's Notes in CHECKPOINTS.md).
 */
const analyzeFixture = analyzeData as AnalyzeResponse;
const trackerFixture = trackerData as TrackerResponse;

// Compile-visible pin (CP-053): the server emits `contact`,
// `litigation_posture` and `note` as bare strings -- `""` when absent,
// never `null` and never an object (`_tracker_item_json`,
// adapters/http/routes.py:181-196; `TrackerItem`, domain/tracker.py:26,
// 31-33). If any of these three fields ever regresses to an optional or
// object type, this block stops compiling.
const contact: string = trackerFixture[0].contact;
const litigationPosture: string = trackerFixture[0].litigation_posture;
const note: string = trackerFixture[2].note;
void contact;
void litigationPosture;
void note;

// Compile-visible pin (CP-053 review attempt 1, finding 1): `project_id` is
// this checkpoint's headline addition to `TrackerItem`. The eight-key test
// below only pins `AnalyzeResponse`'s own keys, and the `as` cast performs no
// excess-property check, so nothing else stops this field from silently
// disappearing. If `project_id` is removed from `TrackerItem`, this line
// stops compiling.
const projectId: string = trackerFixture[0].project_id;
void projectId;

// Compile-visible pin (CP-053 review attempt 1, finding 2): the eight-key
// test below asserts `Object.keys(analyzeFixture)` against a hardcoded list,
// which pins the *fixture*, never the *interface* -- deleting `gcs_uri` from
// `AnalyzeResponse` leaves that assertion, typecheck and all tests green.
// This line stops compiling if `gcs_uri` is removed from `AnalyzeResponse`.
const gcsUri: string = analyzeFixture.gcs_uri;
void gcsUri;

// `tracker_items` is otherwise pinned only incidentally, by
// `analyzeFixture.tracker_items.length` further down -- make that pin
// deliberate too, and to the exact declared element type.
const items: TrackerItem[] = analyzeFixture.tracker_items;
void items;

describe("analyze fixture", () => {
  it("carries at least one scene and one finding", () => {
    expect(analyzeFixture.scenes.length).toBeGreaterThan(0);
    expect(analyzeFixture.findings.length).toBeGreaterThan(0);
  });

  it("carries all eight AnalyzeResponse keys, including gcs_uri and tracker_items", () => {
    expect(Object.keys(analyzeFixture).sort()).toEqual(
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
    expect(analyzeFixture.tracker_items.length).toBeGreaterThan(0);
  });
});

describe("tracker fixture", () => {
  it("covers all three tracker states", () => {
    const states = new Set(trackerFixture.map((item) => item.state));

    expect(states).toEqual(new Set(["BLOCKED", "IN_PROGRESS", "CLEARED"]));
  });

  it("carries the scenario's real contact strings, empty string when absent", () => {
    const contacts = trackerFixture.map((item) => item.contact);

    expect(contacts).toEqual([
      "legal@ferrari.example",
      "sync@warnerchappell.example",
      "",
    ]);
  });
});
