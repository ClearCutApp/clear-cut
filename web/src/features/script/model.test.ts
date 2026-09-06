import { describe, expect, it } from "vitest";

import type { Finding, RiskLevel, Scene, Span, TrackerItem } from "../../api/client";
import {
  applySuggestionFilter,
  buildSuggestions,
  neighbourFindingId,
  scriptLines,
  scriptStats,
  stepperPosition,
  suggestionCounts,
  wordCount,
  zoomIn,
  zoomOut,
  type Suggestion,
} from "./model";

function scene(number: number, text: string, spans: Span[] = []): Scene {
  return {
    number,
    heading: text.split("\n")[0],
    page_start: number,
    page_end: number,
    text,
    content_hash: `hash-${number}`,
    spans,
  };
}

function span(start: number, end: number, findingId: string, risk: RiskLevel = "HIGH"): Span {
  return { scene_number: 1, start, end, finding_id: findingId, risk };
}

function finding(id: string, overrides: Partial<Finding> = {}): Finding {
  return {
    finding_id: id,
    scene_number: 1,
    page: 1,
    raw_text: "flagged",
    category: "COPYRIGHT_WORKS",
    ner_label: null,
    risk_level: "HIGH",
    required_document: "Synchronization License",
    citations: [],
    contradicts: null,
    ...overrides,
  };
}

function item(findingId: string, overrides: Partial<TrackerItem> = {}): TrackerItem {
  return {
    item_id: `item-${findingId}`,
    project_id: "proj_1",
    finding_id: findingId,
    scene_numbers: [1],
    state: "BLOCKED",
    needs_review: false,
    required_document: "Synchronization License",
    contact: "Legal",
    litigation_posture: "",
    draft_email: null,
    note: "",
    updated_at: "2026-09-05T00:00:00Z",
    version: 1,
    ...overrides,
  };
}

function ids(suggestions: Suggestion[]): string[] {
  return suggestions.map((one) => one.finding.finding_id);
}

describe("scriptLines", () => {
  it("cuts the text around one span into unhighlighted, highlighted, unhighlighted", () => {
    const text = "The jukebox plays Hotel California tonight.";
    const start = text.indexOf("Hotel California");
    const lines = scriptLines([scene(1, text, [span(start, start + 16, "EVT-002")])]);

    expect(lines).toHaveLength(1);
    expect(lines[0].runs).toEqual([
      { text: "The jukebox plays ", findingId: null, risk: null },
      { text: "Hotel California", findingId: "EVT-002", risk: "HIGH" },
      { text: " tonight.", findingId: null, risk: null },
    ]);
  });

  it("marks a phrase three times when the analysis sent three spans for it", () => {
    const lines = scriptLines([
      scene(1, "RED. RED. RED.", [
        span(0, 3, "EVT-001", "MEDIUM"),
        span(5, 8, "EVT-001", "MEDIUM"),
        span(10, 13, "EVT-001", "MEDIUM"),
      ]),
    ]);

    const marked = lines[0].runs.filter((run) => run.findingId !== null);
    expect(marked).toHaveLength(3);
    expect(marked.every((run) => run.findingId === "EVT-001")).toBe(true);
  });

  it("counts offsets in code points, so an emoji before a span does not shift it", () => {
    const text = "🎬 Hotel California";
    const start = [...text].indexOf("H");
    const lines = scriptLines([scene(1, text, [span(start, start + 16, "EVT-002")])]);

    expect(lines[0].runs[1].text).toBe("Hotel California");
  });

  it("numbers lines continuously across scenes and keeps blank lines", () => {
    const lines = scriptLines([
      scene(1, "INT. GARAGE - NIGHT\n\nMARCO waits."),
      scene(2, "EXT. ROAD - DAY"),
    ]);

    expect(lines.map((line) => line.number)).toEqual([1, 2, 3, 4]);
    expect(lines.map((line) => line.kind)).toEqual(["slugline", "blank", "action", "slugline"]);
    expect(lines.map((line) => line.sceneNumber)).toEqual([1, 1, 1, 2]);
  });

  it("names an all-caps line ending in TO: a transition", () => {
    const lines = scriptLines([scene(1, "MARCO leaves.\nCUT TO:")]);

    expect(lines[1].kind).toBe("transition");
  });

  it("gives a line the highest risk of the spans on it, and none where there are none", () => {
    const lines = scriptLines([
      scene(1, "low then high", [span(0, 3, "EVT-A", "LOW"), span(9, 13, "EVT-B", "CRITICAL")]),
    ]);

    expect(lines[0].risk).toBe("CRITICAL");
    expect(scriptLines([scene(1, "nothing here")])[0].risk).toBeNull();
  });

  it("drops a span that overlaps one already placed, because a mark cannot nest", () => {
    const lines = scriptLines([
      scene(1, "abcdefgh", [span(0, 4, "EVT-A"), span(2, 6, "EVT-B")]),
    ]);

    expect(lines[0].runs.filter((run) => run.findingId !== null)).toEqual([
      { text: "abcd", findingId: "EVT-A", risk: "HIGH" },
    ]);
  });

  it("ignores a span whose offsets fall outside the scene text", () => {
    const lines = scriptLines([scene(1, "short", [span(3, 99, "EVT-A")])]);

    expect(lines[0].runs).toEqual([{ text: "short", findingId: null, risk: null }]);
  });
});

describe("wordCount", () => {
  it("counts whitespace-separated words across every scene", () => {
    expect(
      wordCount([scene(1, "INT. GARAGE - NIGHT\n\nMARCO waits."), scene(2, "EXT. ROAD")]),
    ).toBe(8);
  });

  it("counts nothing in an empty script", () => {
    expect(wordCount([])).toBe(0);
  });
});

describe("buildSuggestions", () => {
  const scenes = [scene(1, "Hotel California", [span(0, 16, "EVT-002")])];
  const findings = [
    finding("EVT-002"),
    finding("EVT-003", { risk_level: "HIGH", category: "CONTINUITY", page: 8 }),
    finding("EVT-001", { risk_level: "MEDIUM", page: 3 }),
  ];

  it("marks the finding the analysis sent no span for, without inventing a position", () => {
    const byId = new Map(
      buildSuggestions(findings, scenes, []).map((one) => [one.finding.finding_id, one]),
    );

    expect(byId.get("EVT-002")?.hasSpan).toBe(true);
    expect(byId.get("EVT-003")?.hasSpan).toBe(false);
  });

  it("orders findings the way the script reads: scene, then page", () => {
    expect(ids(buildSuggestions(findings, scenes, []))).toEqual(["EVT-002", "EVT-001", "EVT-003"]);
  });

  it("joins each finding to its tracker row, and leaves the state null when there is none", () => {
    const byId = new Map(
      buildSuggestions(findings, scenes, [
        item("EVT-002", { state: "CLEARED", needs_review: true }),
      ]).map((one) => [one.finding.finding_id, one]),
    );

    expect(byId.get("EVT-002")?.state).toBe("CLEARED");
    expect(byId.get("EVT-002")?.needsReview).toBe(true);
    expect(byId.get("EVT-001")?.state).toBeNull();
  });
});

describe("applySuggestionFilter", () => {
  const scenes = [scene(1, "text")];
  const findings = [
    finding("high", { risk_level: "HIGH", page: 1 }),
    finding("consideration", { risk_level: "LOW", page: 2 }),
    finding("done", { risk_level: "MEDIUM", page: 3 }),
  ];
  const suggestions = buildSuggestions(findings, scenes, [item("done", { state: "CLEARED" })]);

  it("passes everything through for All", () => {
    expect(applySuggestionFilter(suggestions, "ALL")).toHaveLength(3);
  });

  it("keeps HIGH and CRITICAL for High risk, and the rest for Considerations", () => {
    expect(ids(applySuggestionFilter(suggestions, "HIGH_RISK"))).toEqual(["high"]);
    expect(ids(applySuggestionFilter(suggestions, "CONSIDERATIONS"))).toEqual([
      "consideration",
      "done",
    ]);
  });

  it("splits To review from Cleared on the tracker state", () => {
    expect(ids(applySuggestionFilter(suggestions, "TO_REVIEW"))).toEqual(["high", "consideration"]);
    expect(ids(applySuggestionFilter(suggestions, "CLEARED"))).toEqual(["done"]);
  });

  it("counts every chip from the whole list, so a narrowed rail never moves them", () => {
    expect(suggestionCounts(suggestions)).toEqual({
      ALL: 3,
      HIGH_RISK: 1,
      TO_REVIEW: 2,
      CONSIDERATIONS: 2,
      CLEARED: 1,
    });
  });
});

describe("the issue stepper", () => {
  const suggestions = buildSuggestions(
    [finding("a", { page: 1 }), finding("b", { page: 2 }), finding("c", { page: 3 })],
    [scene(1, "text")],
    [],
  );

  it("reads a selection as its one-based place in the list", () => {
    expect(stepperPosition(suggestions, "b")).toEqual({ index: 2, total: 3 });
  });

  it("reads no selection, and one outside the list, as no place at all", () => {
    expect(stepperPosition(suggestions, null)).toEqual({ index: 0, total: 3 });
    expect(stepperPosition(suggestions, "elsewhere")).toEqual({ index: 0, total: 3 });
  });

  it("steps to the neighbour and stops at both ends rather than wrapping", () => {
    expect(neighbourFindingId(suggestions, "b", 1)).toBe("c");
    expect(neighbourFindingId(suggestions, "b", -1)).toBe("a");
    expect(neighbourFindingId(suggestions, "c", 1)).toBeNull();
    expect(neighbourFindingId(suggestions, "a", -1)).toBeNull();
  });

  it("starts at the first issue when nothing is selected yet", () => {
    expect(neighbourFindingId(suggestions, null, 1)).toBe("a");
    expect(neighbourFindingId(suggestions, null, -1)).toBe("a");
  });

  it("has no neighbour in an empty list", () => {
    expect(neighbourFindingId([], null, 1)).toBeNull();
  });
});

describe("zoom", () => {
  it("steps up and down a fixed ladder", () => {
    expect(zoomIn(100)).toBe(125);
    expect(zoomOut(100)).toBe(90);
  });

  it("stops at the ends of the ladder", () => {
    expect(zoomIn(200)).toBe(200);
    expect(zoomOut(75)).toBe(75);
  });
});

describe("scriptStats", () => {
  it("counts the scenes, the findings, the high-risk ones and the unmarked ones", () => {
    const scenes = [scene(1, "Hotel California here", [span(0, 16, "EVT-002")])];
    const suggestions = buildSuggestions(
      [
        finding("EVT-002", { risk_level: "HIGH" }),
        finding("EVT-003", { risk_level: "LOW", page: 2 }),
      ],
      scenes,
      [],
    );

    expect(scriptStats(scenes, suggestions)).toEqual({
      scenes: 1,
      findings: 2,
      highRisk: 1,
      unmarked: 1,
      words: 3,
    });
  });
});
