import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QuestionAnswer } from "../../api/client";
import { AnswerPanel } from "./AnswerPanel";

const grounded: QuestionAnswer = {
  text: "Blocked in Argentina:\nEVT-002 needs a synchronization license.",
  facts: [
    {
      fact_id: "FACT-001",
      kind: "LORE",
      text: "Lola's father died before the story begins.",
      source: "Project Bible, character bios, p.2",
    },
  ],
  citations: [
    {
      uri: "https://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/450/texact.htm",
      title: "Ley de Marcas y Designaciones 22.362",
      snippet: "El titular de una marca registrada puede oponerse a su uso.",
    },
  ],
};

describe("AnswerPanel", () => {
  it("keeps the answer's own line breaks", () => {
    render(<AnswerPanel answer={grounded} />);

    expect(
      screen.getByText(grounded.text, { normalizer: (value) => value }),
    ).toBeInTheDocument();
  });

  it("labels each bible fact by kind with its text and source", () => {
    render(<AnswerPanel answer={grounded} />);

    expect(screen.getByRole("heading", { name: "Bible facts" })).toBeInTheDocument();
    expect(screen.getByText("Bible fact")).toBeInTheDocument();
    expect(screen.getByText(grounded.facts[0].text)).toBeInTheDocument();
    expect(screen.getByText(grounded.facts[0].source)).toBeInTheDocument();
  });

  it("links each legal reference to its source with its snippet", () => {
    render(<AnswerPanel answer={grounded} />);

    expect(screen.getByRole("heading", { name: "Legal references" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: grounded.citations[0].title }),
    ).toHaveAttribute("href", grounded.citations[0].uri);
    expect(screen.getByText(grounded.citations[0].snippet)).toBeInTheDocument();
  });

  it("says in words when no facts or references came back", () => {
    render(<AnswerPanel answer={{ text: "Nothing on file.", facts: [], citations: [] }} />);

    expect(screen.getByText("No bible facts were used.")).toBeInTheDocument();
    expect(screen.getByText("No legal references were returned.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).toBeNull();
  });
});
