import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SCRIPT_FIXTURE } from "../../fixtures";
import { FindingFacts } from "./FindingFacts";

const [brandFinding, , continuityFinding] = SCRIPT_FIXTURE.findings;

describe("FindingFacts", () => {
  it("lists the finding's facts as words with its legal references", () => {
    render(<FindingFacts finding={brandFinding} jurisdictionName="Argentina" />);

    expect(screen.getByText("Ferrari Testarossa")).toBeInTheDocument();
    expect(screen.getByText("Industrial property")).toBeInTheDocument();
    expect(screen.getByText("Brand")).toBeInTheDocument();
    expect(screen.getByText("MEDIUM")).toBeInTheDocument();
    expect(screen.getByText("Trademark Clearance Form")).toBeInTheDocument();
    expect(screen.getByText("Argentina")).toBeInTheDocument();
    expect(screen.queryByText(/Contradicts/)).toBeNull();

    const citation = brandFinding.citations[0];
    expect(screen.getByRole("link", { name: citation.title })).toHaveAttribute(
      "href",
      citation.uri,
    );
    expect(screen.getByText(citation.snippet)).toBeInTheDocument();
    expect(screen.queryByText("No legal references were returned.")).toBeNull();
  });

  it("omits the entity row and names the contradicted fact for a continuity finding", () => {
    render(<FindingFacts finding={continuityFinding} jurisdictionName="Argentina" />);

    expect(screen.queryByText("Entity")).toBeNull();
    expect(screen.getByText("Continuity")).toBeInTheDocument();
    expect(screen.getByText("Conflict")).toBeInTheDocument();
    expect(screen.getByText("Contradicts FACT-001")).toBeInTheDocument();
    expect(screen.getByText("No legal references were returned.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
