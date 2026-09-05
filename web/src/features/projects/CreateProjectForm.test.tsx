import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CreateProjectForm } from "./CreateProjectForm";

const JURISDICTIONS = [
  { code: "AR", display_name: "Argentina" },
  { code: "MX", display_name: "Mexico" },
];

interface Options {
  jurisdictions?: typeof JURISDICTIONS | null;
  jurisdictionsError?: string | null;
  submitting?: boolean;
  error?: string | null;
}

function renderForm({
  jurisdictions = JURISDICTIONS,
  jurisdictionsError = null,
  submitting = false,
  error = null,
}: Options = {}) {
  const onSubmit = vi.fn();
  render(
    <CreateProjectForm
      jurisdictions={jurisdictions}
      jurisdictionsError={jurisdictionsError}
      submitting={submitting}
      error={error}
      onSubmit={onSubmit}
    />,
  );
  return onSubmit;
}

describe("CreateProjectForm", () => {
  it("offers the jurisdictions the server returned, by their display names", () => {
    renderForm();

    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Choose a jurisdiction",
      "Argentina",
      "Mexico",
    ]);
  });

  it("submits exactly the two fields the request body has", () => {
    const onSubmit = renderForm();

    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "El Ultimo Verano" },
    });
    fireEvent.change(screen.getByLabelText("Jurisdiction"), { target: { value: "AR" } });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(onSubmit).toHaveBeenCalledWith({
      title: "El Ultimo Verano",
      jurisdiction_code: "AR",
    });
  });

  it("waits, saying so, while the jurisdictions are still on their way", () => {
    renderForm({ jurisdictions: null });

    expect(screen.getByText(/Reading the jurisdictions/)).toBeInTheDocument();
    expect(screen.getByLabelText("Jurisdiction")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create project" })).toBeDisabled();
  });

  it("guesses no code when the jurisdictions could not be read", () => {
    renderForm({ jurisdictions: null, jurisdictionsError: "corpus unavailable" });

    expect(screen.getByText(/No code is guessed here/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("corpus unavailable");
    expect(screen.getByRole("button", { name: "Create project" })).toBeDisabled();
  });

  it("shows the server's refusal next to the button that caused it", () => {
    renderForm({ error: "title is required" });

    expect(screen.getByRole("alert")).toHaveTextContent("title is required");
  });

  it("sits out its own request", () => {
    renderForm({ submitting: true });

    expect(screen.getByRole("button", { name: "Creating…" })).toBeDisabled();
    expect(screen.getByLabelText("Title")).toBeDisabled();
  });

  it("asks for nothing the request body cannot carry", () => {
    renderForm();

    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(screen.getAllByRole("combobox")).toHaveLength(1);
    expect(screen.queryByLabelText(/type|stage|territories|notes/i)).toBeNull();
  });
});
