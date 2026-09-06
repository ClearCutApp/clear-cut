import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Finding, Scene, TrackerItem } from "../../api/client";
import { buildSuggestions } from "./model";
import { SuggestionsRail } from "./SuggestionsRail";

function finding(id: string, overrides: Partial<Finding> = {}): Finding {
  return {
    finding_id: id,
    scene_number: 1,
    page: 1,
    raw_text: id,
    category: "COPYRIGHT_WORKS",
    ner_label: null,
    risk_level: "HIGH",
    required_document: "Synchronization License",
    citations: [],
    contradicts: null,
    ...overrides,
  };
}

const SCENES: Scene[] = [
  {
    number: 1,
    heading: "INT. BAR - NIGHT",
    page_start: 1,
    page_end: 1,
    text: "Hotel California and a prop poster",
    content_hash: "hash-1",
    spans: [
      { scene_number: 1, start: 0, end: 16, finding_id: "marked", risk: "HIGH" },
      { scene_number: 1, start: 21, end: 34, finding_id: "mild", risk: "LOW" },
    ],
  },
];

const FINDINGS = [
  finding("marked", { raw_text: "Hotel California", page: 1 }),
  finding("unmarked", {
    raw_text: "Lola's father, alive and smiling.",
    category: "CONTINUITY",
    contradicts: "FACT-001",
    scene_number: 3,
    page: 8,
  }),
  finding("mild", {
    risk_level: "LOW",
    page: 2,
    raw_text: "a prop poster",
    required_document: "Prop Clearance",
  }),
];

const ITEMS: TrackerItem[] = [
  {
    item_id: "item-mild",
    project_id: "proj_1",
    finding_id: "mild",
    scene_numbers: [1],
    state: "CLEARED",
    needs_review: false,
    required_document: "Prop Clearance",
    contact: "Legal",
    litigation_posture: "",
    draft_email: null,
    note: "",
    updated_at: "2026-09-05T00:00:00Z",
    version: 1,
  },
];

function rail(overrides: Partial<Parameters<typeof SuggestionsRail>[0]> = {}) {
  return render(
    <SuggestionsRail
      suggestions={buildSuggestions(FINDINGS, SCENES, ITEMS)}
      filter="ALL"
      onFilterChange={() => {}}
      selectedFindingId={null}
      onSelectFinding={() => {}}
      {...overrides}
    />,
  );
}

describe("SuggestionsRail", () => {
  it("counts every chip from the whole list", () => {
    rail();

    expect(screen.getByRole("button", { name: /^all/i })).toHaveTextContent("3");
    expect(screen.getByRole("button", { name: /^high risk/i })).toHaveTextContent("2");
    expect(screen.getByRole("button", { name: /^cleared/i })).toHaveTextContent("1");
  });

  it("narrows the list to the chosen chip", () => {
    rail({ filter: "CLEARED" });

    expect(screen.getByText("a prop poster")).toBeInTheDocument();
    expect(screen.queryByText("Hotel California")).toBeNull();
  });

  it("hands the chosen chip back", () => {
    const onFilterChange = vi.fn();
    rail({ onFilterChange });

    fireEvent.click(screen.getByRole("button", { name: /^High risk/ }));

    expect(onFilterChange).toHaveBeenCalledWith("HIGH_RISK");
  });

  it("says so when a filter leaves nothing", () => {
    rail({ suggestions: [], filter: "HIGH_RISK" });

    expect(screen.getByText("No findings match this filter.")).toBeInTheDocument();
  });

  it("lists a finding the paper marks nowhere, with its scene and page", () => {
    rail();

    expect(screen.getByText(/marked nowhere on the page/)).toBeInTheDocument();
    expect(screen.getByText(/Scene 3, page 8/)).toBeInTheDocument();
  });

  it("selects a finding when its card is opened, and clears it when closed again", () => {
    const onSelectFinding = vi.fn();
    const { rerender } = rail({ onSelectFinding });

    fireEvent.click(screen.getByRole("button", { expanded: false, name: /Hotel California/ }));
    expect(onSelectFinding).toHaveBeenCalledWith("marked");

    rerender(
      <SuggestionsRail
        suggestions={buildSuggestions(FINDINGS, SCENES, ITEMS)}
        filter="ALL"
        onFilterChange={() => {}}
        selectedFindingId="marked"
        onSelectFinding={onSelectFinding}
      />,
    );
    fireEvent.click(screen.getByRole("button", { expanded: true }));

    expect(onSelectFinding).toHaveBeenLastCalledWith(null);
  });

  it("shows the analysis's facts only under the open card", () => {
    rail({ selectedFindingId: "unmarked" });

    expect(screen.getByText("Contradicts FACT-001")).toBeVisible();
    expect(screen.getByText("Continuity")).toBeVisible();
    expect(screen.getByText("Prop Clearance")).not.toBeVisible();
  });

  it("says when a finding carries no legal references", () => {
    rail({ selectedFindingId: "marked" });

    expect(screen.getAllByText("No legal references were returned.")[0]).toBeVisible();
  });
});
