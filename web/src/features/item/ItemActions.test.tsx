import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ItemActions } from "./ItemActions";

const UNSERVED_ACTION =
  /assign|suggest|request authorization|find rights holder|mark as resolved|download/i;

describe("ItemActions", () => {
  it("offers Draft email and Notify and reports each click", () => {
    const onDraftEmail = vi.fn();
    const onNotify = vi.fn();
    render(<ItemActions pending={false} onDraftEmail={onDraftEmail} onNotify={onNotify} />);

    fireEvent.click(screen.getByRole("button", { name: "Draft email" }));
    fireEvent.click(screen.getByRole("button", { name: "Notify" }));

    expect(onDraftEmail).toHaveBeenCalledTimes(1);
    expect(onNotify).toHaveBeenCalledTimes(1);
  });

  it("disables both actions while a mutation is in flight", () => {
    render(<ItemActions pending onDraftEmail={vi.fn()} onNotify={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Draft email" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Notify" })).toBeDisabled();
  });

  it("draws no action the API cannot serve", () => {
    render(<ItemActions pending={false} onDraftEmail={vi.fn()} onNotify={vi.fn()} />);

    expect(screen.getAllByRole("button")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: UNSERVED_ACTION })).toBeNull();
  });
});
