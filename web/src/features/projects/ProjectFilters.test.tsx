import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProjectFilters } from "./ProjectFilters";

const TABS = [
  { value: "ALL", code: null, count: 3 },
  { value: "AR", code: "AR", count: 2 },
  { value: "MX", code: "MX", count: 1 },
];

function renderFilters(filter = "ALL") {
  const onFilterChange = vi.fn();
  const onSearchChange = vi.fn();
  render(
    <ProjectFilters
      tabs={TABS}
      filter={filter}
      onFilterChange={onFilterChange}
      search=""
      onSearchChange={onSearchChange}
    />,
  );
  return { onFilterChange, onSearchChange };
}

describe("ProjectFilters", () => {
  it("names each jurisdiction in words and carries its count", () => {
    renderFilters();

    expect(screen.getByRole("tab", { name: "All projects 3" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Argentina 2" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Mexico 1" })).toBeInTheDocument();
  });

  it("marks exactly the chosen tab as selected", () => {
    renderFilters("AR");

    expect(screen.getByRole("tab", { name: "Argentina 2" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "All projects 3" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("reports a chosen tab and a typed query", () => {
    const { onFilterChange, onSearchChange } = renderFilters();

    fireEvent.click(screen.getByRole("tab", { name: "Mexico 1" }));
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "echoes" } });

    expect(onFilterChange).toHaveBeenCalledWith("MX");
    expect(onSearchChange).toHaveBeenCalledWith("echoes");
  });
});
