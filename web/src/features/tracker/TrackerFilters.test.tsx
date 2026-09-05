import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { trackerStats } from "./model";
import { TrackerFilters } from "./TrackerFilters";

const stats = trackerStats([
  { state: "BLOCKED", needs_review: true } as never,
  { state: "IN_PROGRESS", needs_review: false } as never,
  { state: "CLEARED", needs_review: false } as never,
]);

describe("TrackerFilters", () => {
  it("renders five pills carrying the stats counts, and a labelled search", () => {
    render(
      <TrackerFilters
        filter="ALL"
        onFilterChange={vi.fn()}
        search=""
        onSearchChange={vi.fn()}
        stats={stats}
      />,
    );

    expect(screen.getByRole("button", { name: /all/i })).toHaveTextContent("3");
    expect(screen.getByRole("button", { name: /blocked/i })).toHaveTextContent("1");
    expect(screen.getByRole("button", { name: /in progress/i })).toHaveTextContent("1");
    expect(screen.getByRole("button", { name: /cleared/i })).toHaveTextContent("1");
    expect(screen.getByRole("button", { name: /needs review/i })).toHaveTextContent("1");
    expect(screen.getByLabelText(/search/i)).toBeInTheDocument();
  });

  it("marks only the active pill as pressed", () => {
    render(
      <TrackerFilters
        filter="BLOCKED"
        onFilterChange={vi.fn()}
        search=""
        onSearchChange={vi.fn()}
        stats={stats}
      />,
    );

    expect(screen.getByRole("button", { name: /blocked/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: /all/i })).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onFilterChange with the pill's value when clicked", () => {
    const onFilterChange = vi.fn();
    render(
      <TrackerFilters
        filter="ALL"
        onFilterChange={onFilterChange}
        search=""
        onSearchChange={vi.fn()}
        stats={stats}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /cleared/i }));

    expect(onFilterChange).toHaveBeenCalledWith("CLEARED");
  });

  it("calls onSearchChange with the typed value", () => {
    const onSearchChange = vi.fn();
    render(
      <TrackerFilters
        filter="ALL"
        onFilterChange={vi.fn()}
        search=""
        onSearchChange={onSearchChange}
        stats={stats}
      />,
    );

    fireEvent.change(screen.getByLabelText(/search/i), { target: { value: "ferrari" } });

    expect(onSearchChange).toHaveBeenCalledWith("ferrari");
  });
});
