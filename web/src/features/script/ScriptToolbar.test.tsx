import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScriptToolbar } from "./ScriptToolbar";

function toolbar(overrides: Partial<Parameters<typeof ScriptToolbar>[0]> = {}) {
  return render(
    <ScriptToolbar
      words={1234}
      zoom={100}
      onZoomIn={() => {}}
      onZoomOut={() => {}}
      canZoomIn
      canZoomOut
      {...overrides}
    />,
  );
}

describe("ScriptToolbar", () => {
  it("draws every formatting control disabled", () => {
    toolbar();

    for (const label of ["Bold", "Italic", "Underline", "Heading 1", "Code"]) {
      expect(screen.getByRole("button", { name: label })).toBeDisabled();
    }
  });

  it("says why the formatting controls do nothing", () => {
    toolbar();

    expect(screen.getByText(/has no endpoint that writes one/)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Formatting" })).toHaveAccessibleDescription(
      /no endpoint that writes one/,
    );
  });

  it("shows the word count with a thousands separator", () => {
    toolbar();

    expect(screen.getByText("1,234 words")).toBeInTheDocument();
  });

  it("steps the zoom in both directions", () => {
    const onZoomIn = vi.fn();
    const onZoomOut = vi.fn();
    toolbar({ onZoomIn, onZoomOut, zoom: 125 });

    expect(screen.getByText("125%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));

    expect(onZoomIn).toHaveBeenCalledOnce();
    expect(onZoomOut).toHaveBeenCalledOnce();
  });

  it("disables a zoom control at the end of its ladder", () => {
    toolbar({ canZoomIn: false });

    expect(screen.getByRole("button", { name: "Zoom in" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Zoom out" })).toBeEnabled();
  });
});
