import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { IssueStepper } from "./IssueStepper";

const STATS = { scenes: 3, findings: 16, highRisk: 4, unmarked: 1, words: 820 };

function stepper(overrides: Partial<Parameters<typeof IssueStepper>[0]> = {}) {
  return render(
    <IssueStepper
      position={{ index: 4, total: 16 }}
      stats={STATS}
      onPrevious={() => {}}
      onNext={() => {}}
      hasPrevious
      hasNext
      {...overrides}
    />,
  );
}

describe("IssueStepper", () => {
  it("says where the selection sits in the list", () => {
    stepper();

    expect(screen.getByText("4 of 16")).toBeInTheDocument();
  });

  it("says so plainly when nothing is selected yet", () => {
    stepper({ position: { index: 0, total: 16 } });

    expect(screen.getByText("None selected")).toBeInTheDocument();
  });

  it("steps in both directions", () => {
    const onPrevious = vi.fn();
    const onNext = vi.fn();
    stepper({ onPrevious, onNext });

    fireEvent.click(screen.getByRole("button", { name: /Previous issue/ }));
    fireEvent.click(screen.getByRole("button", { name: /Next issue/ }));

    expect(onPrevious).toHaveBeenCalledOnce();
    expect(onNext).toHaveBeenCalledOnce();
  });

  it("disables the button at the end it has reached", () => {
    stepper({ hasNext: false });

    expect(screen.getByRole("button", { name: /Next issue/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Previous issue/ })).toBeEnabled();
  });

  it("carries the counts, including the findings the paper marks nowhere", () => {
    stepper();

    expect(screen.getByText("Not marked").previousSibling).toHaveTextContent("1");
    expect(screen.getByText("High risk").previousSibling).toHaveTextContent("4");
    expect(screen.getByText("Scenes").previousSibling).toHaveTextContent("3");
  });
});
