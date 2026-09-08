import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectMetrics } from "./ProjectMetrics";

const METRICS = { total: 3, jurisdictions: 2, addedThisWeek: 1 };

describe("ProjectMetrics", () => {
  it("shows each number the project list carries under its own label", () => {
    render(<ProjectMetrics metrics={METRICS} />);

    expect(screen.getByText("Projects").previousSibling).toHaveTextContent("3");
    expect(screen.getByText("Jurisdictions").previousSibling).toHaveTextContent("2");
    expect(screen.getByText("Added this week").previousSibling).toHaveTextContent("1");
  });

  it("shows zeroes rather than dashes for an empty server", () => {
    render(
      <ProjectMetrics metrics={{ total: 0, jurisdictions: 0, addedThisWeek: 0 }} />,
    );

    expect(screen.getAllByText("0")).toHaveLength(3);
  });

  it("shows only computed metrics without an unavailable placeholder", () => {
    render(<ProjectMetrics metrics={METRICS} />);

    expect(screen.queryByText("Clearance totals")).toBeNull();
    expect(screen.queryByText(/No endpoint sums them across projects/)).toBeNull();
  });
});
