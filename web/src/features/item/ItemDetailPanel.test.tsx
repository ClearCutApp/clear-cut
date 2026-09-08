import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { SCRIPT_FIXTURE, TRACKER_FIXTURE } from "../../fixtures";
import { ItemDetailPanel, type ItemDetailPanelProps } from "./ItemDetailPanel";

const UNSERVED_ACTION =
  /assign|suggest|request authorization|find rights holder|mark as resolved|download/i;

function renderPanel(overrides: Partial<ItemDetailPanelProps> = {}): ItemDetailPanelProps {
  const props: ItemDetailPanelProps = {
    item: TRACKER_FIXTURE[0],
    finding: SCRIPT_FIXTURE.findings[0],
    jurisdictionName: "Argentina",
    pending: false,
    error: null,
    onStateChange: vi.fn(),
    onDraftEmail: vi.fn(),
    onNotify: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  };
  render(
    <MemoryRouter>
      <ItemDetailPanel {...props} />
    </MemoryRouter>,
  );
  return props;
}

describe("ItemDetailPanel", () => {
  it("shows the item with its badges, finding facts and tracker facts", () => {
    renderPanel();

    const dialog = screen.getByRole("dialog", { name: "EVT-001" });
    expect(dialog).toHaveClass("item-panel");
    expect(within(dialog).getByRole("heading", { name: "EVT-001" })).toBeInTheDocument();
    expect(screen.getByTestId("risk-badge")).toHaveTextContent("MEDIUM");
    expect(screen.getByTestId("state-badge")).toHaveTextContent("BLOCKED");
    expect(screen.getByText("Ferrari Testarossa")).toBeInTheDocument();
    expect(screen.getByText("Industrial property")).toBeInTheDocument();
    expect(screen.getByText("Argentina")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ley de Marcas y Designaciones 22.362" }),
    ).toBeInTheDocument();
    expect(screen.getByText("legal@ferrari.example")).toBeInTheDocument();
    expect(screen.getByLabelText("State")).toHaveValue("BLOCKED");
    expect(screen.getByText(/Version 1/)).toBeInTheDocument();
    expect(screen.queryByText(/no finding in the stored script/)).toBeNull();
  });

  it("explains the missing finding and links to the analysis when the script has none", () => {
    renderPanel({ finding: null });

    expect(
      screen.getByText(/This item has no finding in the stored script/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run analysis" })).toHaveAttribute(
      "href",
      "/projects/demo-project/analyze",
    );
    expect(screen.queryByTestId("risk-badge")).toBeNull();
    expect(screen.queryByText("Legal references")).toBeNull();
    expect(screen.getByTestId("state-badge")).toHaveTextContent("BLOCKED");
    expect(screen.getByLabelText("State")).toBeInTheDocument();
  });

  it("moves focus to Close on open, and closes on click and on Escape", () => {
    const { onClose } = renderPanel();

    const close = screen.getByRole("button", { name: "Close" });
    expect(close).toHaveFocus();

    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(window, { key: "Enter" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("shows a mutation failure inside the dialog", () => {
    renderPanel({ error: "not found" });

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("alert")).toHaveTextContent("not found");
  });

  it("disables the state select and both actions while pending", () => {
    renderPanel({ pending: true });

    expect(screen.getByLabelText("State")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Draft email" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Notify" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Close" })).toBeEnabled();
  });

  it("reports a state change, a draft request and a notify request", () => {
    const { onStateChange, onDraftEmail, onNotify } = renderPanel();

    fireEvent.change(screen.getByLabelText("State"), { target: { value: "IN_PROGRESS" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft email" }));
    fireEvent.change(screen.getByLabelText("Reason to notify the producer"), {
      target: { value: "no answer in 14 days" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Notify" }));

    expect(onStateChange).toHaveBeenCalledWith("IN_PROGRESS");
    expect(onDraftEmail).toHaveBeenCalledTimes(1);
    expect(onNotify).toHaveBeenCalledWith("no answer in 14 days");
  });

  it("draws no button the API cannot serve", () => {
    renderPanel();

    const names = screen
      .getAllByRole("button")
      .map((button) => button.getAttribute("aria-label") ?? button.textContent);
    expect(names).toEqual(["Close", "Draft email", "Notify", "Clearance history"]);
    expect(screen.queryByRole("button", { name: UNSERVED_ACTION })).toBeNull();
  });
});
