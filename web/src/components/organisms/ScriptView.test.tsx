import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalyzeResponse } from "../../api/client";
import analyzeFixture from "../../fixtures/analyze.json";
import { ScriptView } from "./ScriptView";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

const demoProps = {
  analysis: null,
  onAnalyzed: vi.fn(),
  projectId: "demo-project",
  gcsUri: "gs://clearcut-demo/planted-script-v1.pdf",
  jurisdictionCode: "AR",
  version: 1,
};

describe("ScriptView", () => {
  it("submits the analyze request and lifts the response via onAnalyzed", async () => {
    globalThis.fetch = (() =>
      Promise.resolve(
        new Response(JSON.stringify(analyzeFixture), { status: 200 }),
      )) as typeof fetch;
    const onAnalyzed = vi.fn();

    render(<ScriptView {...demoProps} onAnalyzed={onAnalyzed} />);
    screen.getByRole("button", { name: /analyze/i }).click();

    await waitFor(() => expect(onAnalyzed).toHaveBeenCalledTimes(1));
    expect(onAnalyzed).toHaveBeenCalledWith(analyzeFixture);
  });

  it("renders a visible error instead of a blank panel when analyze fails", async () => {
    globalThis.fetch = (() =>
      Promise.resolve(new Response("gcs_uri is required", { status: 400 }))) as typeof fetch;

    render(<ScriptView {...demoProps} />);
    screen.getByRole("button", { name: /analyze/i }).click();

    await waitFor(() =>
      expect(screen.getByText("gcs_uri is required")).toBeInTheDocument(),
    );
  });

  it("renders one SceneCard per scene once an analysis is available", () => {
    render(
      <ScriptView
        {...demoProps}
        analysis={analyzeFixture as AnalyzeResponse}
      />,
    );

    expect(screen.getByText("INT. DINER - DAY")).toBeInTheDocument();
    expect(screen.getByText("EXT. CITY PARK - CONTINUOUS")).toBeInTheDocument();
  });
});
