import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QuestionAnswer } from "../api/client";
import { DEMO_PROJECT } from "../app/demo";
import { EXAMPLE_QUESTIONS } from "../features/ask/model";
import { stubFetch } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { jurisdictionName } from "../theme/jurisdictions";
import { AskView } from "./AskView";

const answer: QuestionAnswer = {
  text: "Blocked in Argentina: EVT-002 needs a synchronization license.",
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

const noTracker = { status: 200, body: [] };

function ask(question: string): void {
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

describe("AskView", () => {
  it("foregrounds voice with project and jurisdiction context", () => {
    stubFetch({ tracker: noTracker });

    renderWithProject(<AskView />);

    expect(screen.getByRole("heading", { name: "Ask ClearCut" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record question" })).toBeDisabled();
    expect(screen.getByText(/Questions for/)).toHaveTextContent(
      jurisdictionName(DEMO_PROJECT.jurisdictionCode),
    );
  });

  it("sends an example question and shows the cited answer", async () => {
    const { calls } = stubFetch({
      tracker: noTracker,
      question: { status: 200, body: answer },
    });

    renderWithProject(<AskView />);
    fireEvent.click(screen.getByRole("button", { name: EXAMPLE_QUESTIONS[0] }));
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText(answer.text)).toBeInTheDocument();
    expect(screen.getByText(answer.facts[0].text)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: answer.citations[0].title }),
    ).toHaveAttribute("href", answer.citations[0].uri);
    expect(calls.find((call) => call.kind === "question")?.body).toMatchObject({
      question: EXAMPLE_QUESTIONS[0],
    });
  });

  it("shows the server's 400 sentence instead of a blank panel", async () => {
    stubFetch({
      tracker: noTracker,
      question: { status: 400, body: "question is required" },
    });

    renderWithProject(<AskView />);
    ask("Can we use the Ferrari brand?");

    expect(await screen.findByRole("alert")).toHaveTextContent("question is required");
    expect(screen.queryByRole("article", { name: "Answer" })).toBeNull();
  });

  it("sends nothing for a blank question", () => {
    const { calls } = stubFetch({
      tracker: noTracker,
      question: { status: 200, body: answer },
    });

    renderWithProject(<AskView />);
    ask("   ");

    expect(calls.filter((call) => call.kind === "question")).toHaveLength(0);
    expect(screen.queryByRole("article", { name: "Answer" })).toBeNull();
  });
});
