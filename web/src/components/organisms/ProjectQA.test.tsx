import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ProjectQA } from "./ProjectQA";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

const groundedAnswer = {
  text: "Argentina requires the rights holder's authorization before a trademarked product airs.",
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

function askQuestion(): void {
  fireEvent.change(screen.getByLabelText(/question/i), {
    target: { value: "Can we use the Ferrari brand?" },
  });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));
}

describe("ProjectQA", () => {
  it("posts the question and renders the grounded answer with its citation", async () => {
    globalThis.fetch = (() =>
      Promise.resolve(
        new Response(JSON.stringify(groundedAnswer), { status: 200 }),
      )) as typeof fetch;

    render(<ProjectQA projectId="demo-project" jurisdictionCode="AR" />);
    askQuestion();

    await waitFor(() =>
      expect(screen.getByText(groundedAnswer.text)).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/Lola's father died before the story begins\./),
    ).toBeInTheDocument();
    const citationLink = screen.getByRole("link", {
      name: "Ley de Marcas y Designaciones 22.362",
    });
    expect(citationLink).toHaveAttribute(
      "href",
      groundedAnswer.citations[0].uri,
    );
  });

  it("renders a visible error instead of a blank panel when the question fails", async () => {
    globalThis.fetch = (() =>
      Promise.resolve(
        new Response("project_id is required", { status: 400 }),
      )) as typeof fetch;

    render(<ProjectQA projectId="demo-project" jurisdictionCode="AR" />);
    askQuestion();

    await waitFor(() =>
      expect(screen.getByText("project_id is required")).toBeInTheDocument(),
    );
  });
});
