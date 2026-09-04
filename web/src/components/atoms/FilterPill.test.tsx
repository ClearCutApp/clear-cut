import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FilterPill } from "./FilterPill";

describe("FilterPill", () => {
  it("reports its active state through aria-pressed", () => {
    const { rerender } = render(
      <FilterPill label="BLOCKED" active onClick={vi.fn()} />,
    );
    expect(screen.getByRole("button", { pressed: true })).toHaveTextContent("BLOCKED");

    rerender(<FilterPill label="BLOCKED" active={false} onClick={vi.fn()} />);
    expect(screen.getByRole("button", { pressed: false })).toBeInTheDocument();
  });

  it("shows the count next to the label when given", () => {
    render(<FilterPill label="CLEARED" count={2} active={false} onClick={vi.fn()} />);

    expect(screen.getByRole("button")).toHaveTextContent("CLEARED2");
  });

  it("shows no count when none is given", () => {
    render(<FilterPill label="ALL" active={false} onClick={vi.fn()} />);

    expect(screen.getByRole("button")).toHaveTextContent(/^ALL$/);
  });

  it("calls onClick when pressed", () => {
    const onClick = vi.fn();
    render(<FilterPill label="ALL" active={false} onClick={onClick} />);

    fireEvent.click(screen.getByRole("button"));

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
