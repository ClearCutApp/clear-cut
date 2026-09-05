import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QuestionForm, type QuestionFormProps } from "./QuestionForm";

const examples = [
  "Do we need permission for the trademark?",
  "What is blocked right now?",
];

function renderForm(overrides: Partial<QuestionFormProps> = {}): ReturnType<typeof vi.fn> {
  const onAsk = vi.fn();
  render(
    <QuestionForm
      examples={examples}
      submitting={false}
      error={null}
      onAsk={onAsk}
      {...overrides}
    />,
  );
  return onAsk;
}

describe("QuestionForm", () => {
  it("fills the question with an example when its chip is clicked", () => {
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: examples[1] }));

    expect(screen.getByLabelText("Question")).toHaveValue(examples[1]);
  });

  it("submits the trimmed question", () => {
    const onAsk = renderForm();

    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "  Can we show the Ferrari?  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(onAsk).toHaveBeenCalledWith("Can we show the Ferrari?");
  });

  it("does not submit a blank question", () => {
    const onAsk = renderForm();

    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(onAsk).not.toHaveBeenCalled();
  });

  it("holds the button while a question is in flight", () => {
    renderForm({ submitting: true });

    expect(screen.getByRole("button", { name: "Asking…" })).toBeDisabled();
  });

  it("shows the failure as an alert", () => {
    renderForm({ error: "jurisdiction_code is required" });

    expect(screen.getByRole("alert")).toHaveTextContent("jurisdiction_code is required");
  });

  it("offers no microphone and no web search control", () => {
    renderForm();

    expect(screen.getAllByRole("button")).toHaveLength(examples.length + 1);
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.queryByLabelText(/web search|microphone|voice/i)).toBeNull();
  });
});
