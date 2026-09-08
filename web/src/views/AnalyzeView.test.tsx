import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AnalysisJob, AnalysisState, ScriptSummary } from "../api/client";
import { SCRIPT_FIXTURE } from "../fixtures";
import { deferredResponse, stubFetch, type StubRoute } from "../testing/fetchStub";
import { renderWithProject } from "../testing/renderWithProject";
import { AnalyzeView } from "./AnalyzeView";

const ANALYZE_PATH = "/projects/proj_1/analyze";

const SUMMARY: ScriptSummary = {
  script_id: SCRIPT_FIXTURE.script_id,
  project_id: SCRIPT_FIXTURE.project_id,
  version: 2,
  gcs_uri: SCRIPT_FIXTURE.gcs_uri,
  jurisdiction_code: SCRIPT_FIXTURE.jurisdiction_code,
  scene_count: 3,
  finding_count: 3,
};

function jobIn(state: AnalysisState, error = ""): AnalysisJob {
  return {
    analysis_id: "ana_1",
    project_id: "proj_1",
    script_id: SCRIPT_FIXTURE.script_id,
    state,
    created_at: "2026-09-05T12:00:00Z",
    updated_at: "2026-09-05T12:00:00Z",
    error,
    version: 1,
  };
}

function ok(body: unknown) {
  return { status: 200, body };
}

function renderAnalyze(routes: Record<string, StubRoute> = {}) {
  const stub = stubFetch({ tracker: ok([]), scripts: ok([]), ...routes });
  renderWithProject(<AnalyzeView />, { path: ANALYZE_PATH });
  return stub;
}

async function fillUri(uri: string): Promise<void> {
  fireEvent.change(await screen.findByLabelText("Script URI"), { target: { value: uri } });
}

describe("AnalyzeView", () => {
  it("says how long the run takes and that it outlives this page", () => {
    renderAnalyze();

    expect(screen.getByRole("heading", { name: "Run analysis" })).toBeInTheDocument();
    expect(screen.getByText(/takes minutes on a feature/)).toBeInTheDocument();
    expect(screen.getByText(/continues on the server/)).toBeInTheDocument();
  });

  it("waits for the stored versions rather than opening at one it may have to change", () => {
    renderAnalyze({ scripts: deferredResponse().route });

    expect(screen.getByText(/Reading the versions already stored/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Version")).toBeNull();
  });

  it("offers version 1 for a project with no stored script", async () => {
    renderAnalyze();

    expect(await screen.findByLabelText("Version")).toHaveValue(1);
  });

  it("offers the version after the newest stored one", async () => {
    renderAnalyze({ scripts: ok([SUMMARY]), script: ok(SCRIPT_FIXTURE) });

    expect(await screen.findByLabelText("Version")).toHaveValue(3);
  });

  it("says the version is not derived when the stored versions could not be read", async () => {
    renderAnalyze({ scripts: { status: 500, body: "storage unavailable" } });

    expect(await screen.findByText(/not derived from them/)).toBeInTheDocument();
    expect(screen.getByLabelText("Version")).toHaveValue(1);
  });

  it("queues the analysis, waits for the job and opens the tracker", async () => {
    const { calls } = renderAnalyze({
      "create-script": ok(jobIn("QUEUED")),
      analysis: [ok(jobIn("RUNNING")), ok(jobIn("SUCCEEDED"))],
      script: ok(SCRIPT_FIXTURE),
    });

    await fillUri("gs://bucket/script.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/projects/proj_1"),
    );
    expect(calls.find((call) => call.kind === "create-script")?.body).toMatchObject({
      gcs_uri: "gs://bucket/script.pdf",
      version: 1,
    });
    expect(calls.filter((call) => call.kind === "analysis").length).toBeGreaterThan(0);
  });

  it("keeps the reader here and shows the job's own reason when the run fails", async () => {
    renderAnalyze({
      "create-script": ok(jobIn("QUEUED")),
      analysis: ok(jobIn("FAILED", "Document AI returned no pages")),
    });

    await fillUri("gs://bucket/script.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Document AI returned no pages",
    );
    expect(screen.getByTestId("location")).toHaveTextContent(ANALYZE_PATH);
  });

  it("shows the refusal when the queue itself is rejected", async () => {
    renderAnalyze({ "create-script": { status: 400, body: "gcs_uri is required" } });

    await fillUri("x");
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("gcs_uri is required");
  });

  it("analyzes the owned file ID returned by an upload", async () => {
    const { calls } = renderAnalyze({
      "upload-script": ok({ file_id: "file-owned", gcs_uri: "gs://bucket/original.pdf",
        filename: "draft.pdf", size_bytes: 9, content_type: "application/pdf" }),
      "create-script": { status: 503, body: "worker unavailable" },
    });
    fireEvent.change(screen.getByLabelText("Screenplay PDF"), {
      target: { files: [new File(["%PDF-test"], "draft.pdf", { type: "application/pdf" })] },
    });
    await waitFor(() => expect(screen.getByLabelText("Script URI")).toHaveValue(
      "gs://bucket/original.pdf",
    ));
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await waitFor(() => expect(calls.find((call) => call.kind === "create-script")?.body)
      .toMatchObject({ file_id: "file-owned" }));
  });

});
