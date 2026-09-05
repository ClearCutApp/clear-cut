import { describe, expect, it } from "vitest";

import type { TrackerItem } from "../../api/client";
import trackerFixture from "../../fixtures/tracker.json";
import {
  applyFilter,
  groupByState,
  searchItems,
  sceneLabel,
  trackerStats,
} from "./model";

const items = trackerFixture as TrackerItem[];

function withState(item: TrackerItem, overrides: Partial<TrackerItem>): TrackerItem {
  return { ...item, ...overrides };
}

describe("sceneLabel", () => {
  it("names a single scene in the singular", () => {
    expect(sceneLabel([1])).toBe("Scene 1");
  });

  it("names several scenes in the plural, joined in order", () => {
    expect(sceneLabel([1, 3])).toBe("Scenes 1, 3");
  });
});

describe("trackerStats", () => {
  it("counts every state and needs_review across all three fixture rows", () => {
    const stats = trackerStats(items);

    expect(stats).toEqual({
      total: 3,
      cleared: 0,
      clearedPercent: 0,
      inProgress: 0,
      blocked: 3,
      needsReview: 0,
    });
  });

  it("rounds the cleared percent once some rows clear", () => {
    const mixed = [
      withState(items[0], { state: "CLEARED" }),
      withState(items[1], { state: "BLOCKED" }),
      withState(items[2], { state: "IN_PROGRESS" }),
    ];

    expect(trackerStats(mixed).clearedPercent).toBe(33);
  });

  it("reports zero for every field on an empty tracker", () => {
    expect(trackerStats([])).toEqual({
      total: 0,
      cleared: 0,
      clearedPercent: 0,
      inProgress: 0,
      blocked: 0,
      needsReview: 0,
    });
  });
});

describe("groupByState", () => {
  it("groups the three BLOCKED fixture rows under one BLOCKED group", () => {
    const groups = groupByState(items);

    expect(groups).toEqual([{ state: "BLOCKED", items }]);
  });

  it("orders present groups BLOCKED, then IN_PROGRESS, then CLEARED", () => {
    const mixed = [
      withState(items[0], { state: "CLEARED" }),
      withState(items[1], { state: "IN_PROGRESS" }),
      withState(items[2], { state: "BLOCKED" }),
    ];

    expect(groupByState(mixed).map((group) => group.state)).toEqual([
      "BLOCKED",
      "IN_PROGRESS",
      "CLEARED",
    ]);
  });

  it("omits a state with no items rather than emitting an empty group", () => {
    expect(groupByState(items).some((group) => group.state === "CLEARED")).toBe(false);
  });
});

describe("applyFilter", () => {
  it("passes every item through for ALL", () => {
    expect(applyFilter(items, "ALL")).toEqual(items);
  });

  it("narrows to the matching state", () => {
    const mixed = [
      withState(items[0], { state: "CLEARED" }),
      withState(items[1], { state: "BLOCKED" }),
    ];

    expect(applyFilter(mixed, "CLEARED")).toEqual([mixed[0]]);
  });

  it("narrows to items flagged needs_review for NEEDS_REVIEW", () => {
    const flagged = withState(items[0], { needs_review: true });

    expect(applyFilter([flagged, items[1]], "NEEDS_REVIEW")).toEqual([flagged]);
  });
});

describe("searchItems", () => {
  it("matches on required_document case-insensitively", () => {
    expect(searchItems(items, "trademark")).toEqual([items[0]]);
  });

  it("matches on contact", () => {
    expect(searchItems(items, "warnerchappell")).toEqual([items[1]]);
  });

  it("matches on finding_id", () => {
    expect(searchItems(items, "evt-003")).toEqual([items[2]]);
  });

  it("matches on the scene label", () => {
    expect(searchItems(items, "scene 2")).toEqual([items[1]]);
  });

  it("returns every item for a blank query", () => {
    expect(searchItems(items, "   ")).toEqual(items);
  });

  it("returns no items when nothing matches", () => {
    expect(searchItems(items, "nonexistent")).toEqual([]);
  });
});
