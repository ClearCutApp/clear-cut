import { describe, expect, it } from "vitest";

import type { ScriptViewResponse, TrackerResponse } from "../api/client";
import scriptViewData from "./script-view.json";
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
const scriptViewFixture = scriptViewData as ScriptViewResponse;
const trackerFixture = trackerData as TrackerResponse;

describe("script-view fixture", () => {
  it("carries at least one scene and one finding", () => {
    expect(scriptViewFixture.scenes.length).toBeGreaterThan(0);
    expect(scriptViewFixture.findings.length).toBeGreaterThan(0);
  });
});

describe("tracker fixture", () => {
  it("covers all three tracker states", () => {
    const states = new Set(trackerFixture.map((item) => item.state));

    expect(states).toEqual(new Set(["BLOCKED", "IN_PROGRESS", "CLEARED"]));
  });
});
