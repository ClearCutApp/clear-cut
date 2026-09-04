import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows the worded title", () => {
    render(<EmptyState title="No analysis has run yet for this project." />);

    expect(
      screen.getByText("No analysis has run yet for this project."),
    ).toBeInTheDocument();
  });

  it("renders the way out it is given", () => {
    render(
      <EmptyState title="Nothing here.">
        <a href="#run">Run analysis</a>
      </EmptyState>,
    );

    expect(screen.getByRole("link", { name: "Run analysis" })).toBeInTheDocument();
  });
});
