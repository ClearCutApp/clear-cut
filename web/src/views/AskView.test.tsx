import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { stubFetch } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { AskView } from "./AskView";

describe("AskView", () => {
  it("is headed as the place to ask", () => {
    stubFetch({ tracker: { status: 200, body: [] } });

    renderWithProject(<AskView />);

    expect(screen.getByRole("heading", { name: "Ask" })).toBeInTheDocument();
  });
});
