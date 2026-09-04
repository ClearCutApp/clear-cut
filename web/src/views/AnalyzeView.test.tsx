import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { stubFetch } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { AnalyzeView } from "./AnalyzeView";

describe("AnalyzeView", () => {
  it("is headed as the place to run an analysis", () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<AnalyzeView />);

    expect(screen.getByRole("heading", { name: "Run analysis" })).toBeInTheDocument();
  });
});
