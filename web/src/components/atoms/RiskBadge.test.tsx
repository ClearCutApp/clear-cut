import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RiskBadge } from "./RiskBadge";

describe("RiskBadge", () => {
  it.each([
    ["LOW", "LOW"],
    ["MEDIUM", "MEDIUM"],
    ["HIGH", "HIGH"],
    ["CRITICAL", "CRITICAL"],
  ] as const)("renders %s as the word %s", (risk, expectedText) => {
    render(<RiskBadge risk={risk} />);

    expect(screen.getByText(expectedText)).toBeInTheDocument();
  });

  it("renders a distinct label for each risk level", () => {
    const labels = (["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const).map(
      (risk) => {
        const { unmount } = render(<RiskBadge risk={risk} />);
        const text = screen.getByTestId("risk-badge").textContent;
        unmount();
        return text;
      },
    );

    expect(new Set(labels).size).toBe(labels.length);
  });
});
