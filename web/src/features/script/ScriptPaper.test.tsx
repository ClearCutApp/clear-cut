import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Scene, Span } from "../../api/client";
import { scriptLines } from "./model";
import { ScriptPaper } from "./ScriptPaper";

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

const SCENE_TEXT = 'INT. ROADSIDE BAR - NIGHT\nThe jukebox plays "Hotel California".';
/** The scene is plain ASCII, so a string index is also its code-point
 * offset -- which is what the server sends (ADR 0015). */
const HOTEL_START = SCENE_TEXT.indexOf("Hotel California");

function paper(overrides: Partial<Parameters<typeof ScriptPaper>[0]> = {}) {
  const lines = scriptLines([
    scene(1, SCENE_TEXT, [
      {
        scene_number: 1,
        start: HOTEL_START,
        end: HOTEL_START + 16,
        finding_id: "EVT-002",
        risk: "HIGH",
      },
    ]),
  ]);
  return render(
    <ScriptPaper
      lines={lines}
      selectedFindingId={null}
      onSelectFinding={() => {}}
      zoom={100}
      {...overrides}
    />,
  );
}

describe("ScriptPaper", () => {
  it("prints the script with the flagged phrase as its own control", () => {
    paper();

    expect(screen.getByText("INT. ROADSIDE BAR - NIGHT")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hotel California" })).toBeInTheDocument();
  });

  it("hands the finding id back when a highlight is clicked", () => {
    const onSelectFinding = vi.fn();
    paper({ onSelectFinding });

    fireEvent.click(screen.getByRole("button", { name: "Hotel California" }));

    expect(onSelectFinding).toHaveBeenCalledWith("EVT-002");
  });

  it("presses the highlight of the selected finding and no other", () => {
    paper({ selectedFindingId: "EVT-002" });

    expect(screen.getByRole("button", { name: "Hotel California" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("names the gutter dot's risk in words, never by colour alone", () => {
    paper();

    expect(screen.getByRole("img", { name: "HIGH risk on line 2" })).toBeInTheDocument();
  });

  it("leaves a line with no finding without a dot", () => {
    paper();

    expect(screen.queryByRole("img", { name: /risk on line 1$/ })).toBeNull();
  });

  it("carries the zoom percentage as a custom property rather than a font size", () => {
    const { container } = paper({ zoom: 125 });

    expect(container.querySelector(".script-paper")).toHaveStyle({ "--script-zoom": "125%" });
  });
});
