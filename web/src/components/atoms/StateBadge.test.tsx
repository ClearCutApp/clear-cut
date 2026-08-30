import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StateBadge } from "./StateBadge";

describe("StateBadge", () => {
  it.each([
    ["BLOCKED", "BLOCKED"],
    ["IN_PROGRESS", "IN_PROGRESS"],
    ["CLEARED", "CLEARED"],
  ] as const)("renders %s as the word %s", (state, expectedText) => {
    render(<StateBadge state={state} />);

    expect(screen.getByText(expectedText)).toBeInTheDocument();
  });

  it("renders a distinct label for each tracker state", () => {
    const labels = (["BLOCKED", "IN_PROGRESS", "CLEARED"] as const).map(
      (state) => {
        const { unmount } = render(<StateBadge state={state} />);
        const text = screen.getByTestId("state-badge").textContent;
        unmount();
        return text;
      },
    );

    expect(new Set(labels).size).toBe(labels.length);
  });
});
