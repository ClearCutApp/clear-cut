import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Finding, Scene } from "../../api/client";
import { SceneCard } from "./SceneCard";

const scene: Scene = {
  number: 1,
  heading: "INT. GARAGE - NIGHT",
  page_start: 3,
  page_end: 3,
  text: "MARCO wipes down his cherry-red Ferrari Testarossa.",
  content_hash: "a".repeat(64),
  spans: [],
};

const trademarkFinding: Finding = {
  finding_id: "SEED-FERRARI",
  scene_number: 1,
  page: 3,
  raw_text: "Ferrari Testarossa",
  category: "INDUSTRIAL_PROPERTY",
  ner_label: "BRAND",
  risk_level: "MEDIUM",
  required_document: "Trademark Clearance Form",
  citations: [
    {
      uri: "https://www.ferrari.com/en-EN/legal",
      title: "Ferrari Trademark Notice",
      snippet: "The Ferrari trademarks may not be used without consent.",
    },
  ],
  contradicts: null,
};

const continuityFinding: Finding = {
  finding_id: "SEED-CONTINUITY",
  scene_number: 3,
  page: 8,
  raw_text: "Lola's father walks through the front door, alive and smiling.",
  category: "CONTINUITY",
  ner_label: null,
  risk_level: "HIGH",
  required_document: "Continuity Revision",
  citations: [],
  contradicts: "FACT-001",
};

describe("SceneCard", () => {
  it("renders the scene heading, page range, and each finding's badge, category, document, and citation", () => {
    render(<SceneCard scene={scene} findings={[trademarkFinding]} />);

    expect(screen.getByText("INT. GARAGE - NIGHT")).toBeInTheDocument();
    expect(screen.getByText("MEDIUM")).toBeInTheDocument();
    expect(screen.getByText("INDUSTRIAL_PROPERTY")).toBeInTheDocument();
    expect(screen.getByText(/Trademark Clearance Form/)).toBeInTheDocument();
    const citationLink = screen.getByRole("link", {
      name: "Ferrari Trademark Notice",
    });
    expect(citationLink).toHaveAttribute(
      "href",
      "https://www.ferrari.com/en-EN/legal",
    );
    expect(
      screen.getByText(/The Ferrari trademarks may not be used/),
    ).toBeInTheDocument();
  });

  it("renders the contradicted fact id for the continuity finding", () => {
    render(<SceneCard scene={scene} findings={[continuityFinding]} />);

    expect(screen.getByText(/FACT-001/)).toBeInTheDocument();
  });

  it("renders a worded message when the scene has no findings", () => {
    render(<SceneCard scene={scene} findings={[]} />);

    expect(screen.getByText(/no findings/i)).toBeInTheDocument();
  });
});
