import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type { AnalysisJob, AnalysisState, Script } from "../api/client";
import { DEMO_PROJECT } from "../app/demo";
import { SCRIPT_FIXTURE, TRACKER_FIXTURE } from "../fixtures";
import { deferredResponse, stubFetch } from "../testing/fetchStub";
import { ProjectProvider, useProject } from "./ProjectContext";
import { readRecentProjects, rememberProject } from "./recentProjects";

const request = { gcs_uri: "gs://bucket/script.pdf", version: 1, jurisdiction_code: "US" };

const PROJECT = {
  project_id: "proj_1",
  title: "El Ultimo Verano",
  jurisdiction_code: "AR",
  created_at: "2026-09-01T10:00:00Z",
};

const SCRIPT_SUMMARY = {
  script_id: SCRIPT_FIXTURE.script_id,
  project_id: SCRIPT_FIXTURE.project_id,
  version: SCRIPT_FIXTURE.version,
  gcs_uri: SCRIPT_FIXTURE.gcs_uri,
  jurisdiction_code: SCRIPT_FIXTURE.jurisdiction_code,
  scene_count: SCRIPT_FIXTURE.scenes.length,
  finding_count: SCRIPT_FIXTURE.findings.length,
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

/** The poll's waits are the policy's, and `features/analysis/model` proves
 * them. Here they are skipped so the wiring is what the test spends time on. */
const noWait = () => Promise.resolve();

function wrapperFor(projectId: string, initialAnalysis: Script | null = null) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ProjectProvider
        projectId={projectId}
        initialAnalysis={initialAnalysis}
        pollWait={noWait}
      >
        {children}
      </ProjectProvider>
    );
  };
}

function ok(body: unknown) {
  return { status: 200, body };
}

async function renderLoaded(initialAnalysis: Script | null = null) {
  const hook = renderHook(useProject, { wrapper: wrapperFor("proj_1", initialAnalysis) });
  await waitFor(() => expect(hook.result.current.tracker).not.toBeNull());
  return hook;
}

describe("ProjectProvider tracker", () => {
  it("starts with no tracker and fills it from the mount GET", async () => {
    stubFetch({ tracker: ok(TRACKER_FIXTURE) });

    const { result } = renderHook(useProject, { wrapper: wrapperFor("proj_1") });

    expect(result.current.tracker).toBeNull();
    await waitFor(() => expect(result.current.tracker).toHaveLength(3));
    expect(result.current.trackerError).toBeNull();
  });

  it("exposes the server's sentence when the mount GET fails", async () => {
    stubFetch({ tracker: { status: 500, body: "internal error" } });

    const { result } = renderHook(useProject, { wrapper: wrapperFor("proj_1") });

    await waitFor(() => expect(result.current.trackerError).toBe("internal error"));
    expect(result.current.tracker).toBeNull();
  });

  it("re-reads the tracker on refreshTracker", async () => {
    const { calls } = stubFetch({ tracker: [ok([]), ok(TRACKER_FIXTURE)] });
    const { result } = await renderLoaded();

    await act(() => result.current.refreshTracker());

    expect(result.current.tracker).toHaveLength(3);
    expect(calls.filter((call) => call.kind === "tracker")).toHaveLength(2);
  });
});

describe("ProjectProvider project", () => {
  it("fills the project from its own GET and takes the jurisdiction from it", async () => {
    stubFetch({ tracker: ok([]), project: ok(PROJECT) });
    const { result } = await renderLoaded();

    await waitFor(() => expect(result.current.project).toEqual(PROJECT));
    expect(result.current.jurisdictionCode).toBe("AR");
    expect(result.current.projectError).toBeNull();
  });

  it("keeps the tracker on screen when the project read fails", async () => {
    stubFetch({ tracker: ok(TRACKER_FIXTURE), project: { status: 404, body: "no such project" } });
    const { result } = await renderLoaded();

    await waitFor(() => expect(result.current.projectError).toBe("no such project"));
    expect(result.current.project).toBeNull();
    expect(result.current.tracker).toHaveLength(3);
  });
});

describe("ProjectProvider stored scripts", () => {
  it("reads the newest stored version so a finding survives a reload", async () => {
    const { calls } = stubFetch({
      tracker: ok(TRACKER_FIXTURE),
      scripts: ok([SCRIPT_SUMMARY]),
      script: ok(SCRIPT_FIXTURE),
    });
    const { result } = await renderLoaded();

    await waitFor(() => expect(result.current.analysis).toEqual(SCRIPT_FIXTURE));
    expect(result.current.scripts).toEqual([SCRIPT_SUMMARY]);
    expect(calls.filter((call) => call.kind === "script")).toHaveLength(1);
  });

  it("reads no version and reports no error when the project has none", async () => {
    const { calls } = stubFetch({ tracker: ok([]), scripts: ok([]) });
    const { result } = await renderLoaded();

    await waitFor(() => expect(result.current.scripts).toEqual([]));
    expect(result.current.analysis).toBeNull();
    expect(result.current.analysisError).toBeNull();
    expect(calls.some((call) => call.kind === "script")).toBe(false);
  });

  it("exposes the server's sentence when the version list fails", async () => {
    stubFetch({ tracker: ok([]), scripts: { status: 500, body: "storage unavailable" } });
    const { result } = await renderLoaded();

    await waitFor(() => expect(result.current.analysisError).toBe("storage unavailable"));
  });
});

describe("ProjectProvider runAnalysis", () => {
  it("polls the queued job, then reads the script it produced and re-reads the tracker", async () => {
    const { calls } = stubFetch({
      tracker: [ok([]), ok(TRACKER_FIXTURE)],
      scripts: ok([]),
      "create-script": ok(jobIn("QUEUED")),
      analysis: [ok(jobIn("RUNNING")), ok(jobIn("SUCCEEDED"))],
      script: ok(SCRIPT_FIXTURE),
    });
    rememberProject("proj_1", "US");
    const { result } = await renderLoaded();

    let outcome;
    await act(async () => {
      outcome = await result.current.runAnalysis(request);
    });

    expect(outcome).toEqual({ ok: true, value: SCRIPT_FIXTURE });
    expect(result.current.analysis).toEqual(SCRIPT_FIXTURE);
    expect(result.current.job?.state).toBe("SUCCEEDED");
    expect(result.current.jurisdictionCode).toBe(SCRIPT_FIXTURE.jurisdiction_code);
    expect(calls.filter((call) => call.kind === "analysis")).toHaveLength(2);
    await waitFor(() => expect(result.current.tracker).toHaveLength(3));
  });

  it("returns the 400 body as the message and never starts polling", async () => {
    const { calls } = stubFetch({
      tracker: ok([]),
      scripts: ok([]),
      "create-script": { status: 400, body: "gcs_uri is required" },
    });
    const { result } = await renderLoaded();

    let outcome;
    await act(async () => {
      outcome = await result.current.runAnalysis(request);
    });

    expect(outcome).toEqual({ ok: false, message: "gcs_uri is required" });
    expect(result.current.analysis).toBeNull();
    expect(calls.some((call) => call.kind === "analysis")).toBe(false);
  });

  it("reports the job's own error when the run fails, and reads no script", async () => {
    const { calls } = stubFetch({
      tracker: ok([]),
      scripts: ok([]),
      "create-script": ok(jobIn("QUEUED")),
      analysis: ok(jobIn("FAILED", "Document AI returned no pages")),
    });
    const { result } = await renderLoaded();

    let outcome;
    await act(async () => {
      outcome = await result.current.runAnalysis(request);
    });

    expect(outcome).toEqual({ ok: false, message: "Document AI returned no pages" });
    expect(result.current.analysis).toBeNull();
    expect(calls.some((call) => call.kind === "script")).toBe(false);
  });
});

describe("ProjectProvider mutations", () => {
  it("changeState replaces exactly that row from the PATCH response, even when the response state differs", async () => {
    const patched = { ...TRACKER_FIXTURE[1], state: "CLEARED" as const, version: 2 };
    const { calls } = stubFetch({ tracker: ok(TRACKER_FIXTURE), patch: ok(patched) });
    const { result } = await renderLoaded();

    await act(() => result.current.changeState("EVT-002", "IN_PROGRESS"));

    expect(result.current.tracker?.[1]).toEqual(patched);
    expect(result.current.tracker?.[0]).toEqual(TRACKER_FIXTURE[0]);
    expect(result.current.tracker?.[2]).toEqual(TRACKER_FIXTURE[2]);
    expect(calls.find((call) => call.kind === "patch")?.body).toEqual({ state: "IN_PROGRESS", expected_version: 1 });
  });

  it("draftEmail replaces the row with the returned draft_email", async () => {
    const drafted = { ...TRACKER_FIXTURE[0], draft_email: "Dear Ferrari S.p.A., ..." };
    const { calls } = stubFetch({ tracker: ok(TRACKER_FIXTURE), "email-draft": ok(drafted) });
    const { result } = await renderLoaded();

    await act(() => result.current.draftEmail("EVT-001"));

    expect(result.current.tracker?.[0].draft_email).toBe("Dear Ferrari S.p.A., ...");
    expect(calls.find((call) => call.kind === "email-draft")?.body).toEqual({ expected_version: 1 });
  });

  it("notify sends the producer's reason and leaves the row as the server returned it", async () => {
    const { calls } = stubFetch({
      tracker: ok(TRACKER_FIXTURE),
      notification: ok(TRACKER_FIXTURE[2]),
    });
    const { result } = await renderLoaded();

    await act(() => result.current.notify("EVT-003", "no answer in 14 days"));

    expect(result.current.tracker).toEqual(TRACKER_FIXTURE);
    expect(calls.find((call) => call.kind === "notification")?.body).toEqual({
      reason: "no answer in 14 days",
    });
  });

  it("marks the item pending while its request is in flight and clears it after", async () => {
    const deferred = deferredResponse();
    stubFetch({ tracker: ok(TRACKER_FIXTURE), "email-draft": deferred.route });
    const { result } = await renderLoaded();

    let mutation: Promise<unknown> = Promise.resolve();
    act(() => {
      mutation = result.current.draftEmail("EVT-001");
    });

    await waitFor(() => expect(result.current.pendingItemIds.has("EVT-001")).toBe(true));
    deferred.resolve(ok(TRACKER_FIXTURE[0]));
    await act(() => mutation);
    expect(result.current.pendingItemIds.has("EVT-001")).toBe(false);
  });

  it("reports a failed mutation as a message, keeps the row and clears pending", async () => {
    stubFetch({ tracker: ok(TRACKER_FIXTURE), patch: { status: 404, body: "not found" } });
    const { result } = await renderLoaded();

    let outcome;
    await act(async () => {
      outcome = await result.current.changeState("EVT-001", "CLEARED");
    });

    expect(outcome).toEqual({ ok: false, message: "not found" });
    expect(result.current.tracker?.[0]).toEqual(TRACKER_FIXTURE[0]);
    expect(result.current.pendingItemIds.size).toBe(0);
  });
});

describe("ProjectProvider ask", () => {
  it("posts the question under the current jurisdiction and returns the answer", async () => {
    const answer = { text: "Yes.", facts: [], citations: [] };
    const { calls } = stubFetch({ tracker: ok([]), question: ok(answer) });
    const { result } = await renderLoaded();

    act(() => result.current.setJurisdiction("ES"));
    let outcome;
    await act(async () => {
      outcome = await result.current.ask("Do we need permission?");
    });

    expect(outcome).toEqual({ ok: true, value: answer });
    expect(calls.find((call) => call.kind === "question")?.body).toEqual({
      jurisdiction_code: "ES",
      question: "Do we need permission?",
    });
  });
});

describe("ProjectProvider selection and joins", () => {
  it("selects and clears an item", async () => {
    stubFetch({ tracker: ok(TRACKER_FIXTURE) });
    const { result } = await renderLoaded();

    act(() => result.current.selectItem("EVT-002"));
    expect(result.current.selectedItemId).toBe("EVT-002");

    act(() => result.current.selectItem(null));
    expect(result.current.selectedItemId).toBeNull();
  });

  it("joins an item to its finding and a finding to its item through the loaded script", async () => {
    stubFetch({ tracker: ok(TRACKER_FIXTURE) });
    const { result } = await renderLoaded(SCRIPT_FIXTURE);

    expect(result.current.findingFor("EVT-003")?.contradicts).toBe("FACT-001");
    expect(result.current.itemFor("EVT-001")?.item_id).toBe("EVT-001");
    expect(result.current.findingFor("missing")).toBeNull();
    expect(result.current.itemFor("missing")).toBeNull();
  });

  it("finds no finding without a script loaded", async () => {
    stubFetch({ tracker: ok(TRACKER_FIXTURE), scripts: ok([]) });
    const { result } = await renderLoaded();

    expect(result.current.findingFor("EVT-001")).toBeNull();
  });
});

describe("ProjectProvider jurisdiction and memory", () => {
  it("starts from the remembered jurisdiction when the browser has one", async () => {
    stubFetch({ tracker: ok([]) });
    rememberProject("proj_1", "MX");

    const { result } = await renderLoaded();

    expect(result.current.jurisdictionCode).toBe("MX");
  });

  it("falls back to the demo jurisdiction for a project this browser never opened", async () => {
    stubFetch({ tracker: ok([]) });

    const { result } = await renderLoaded();

    expect(result.current.jurisdictionCode).toBe(DEMO_PROJECT.jurisdictionCode);
  });

  it("remembers the project on mount, because a deep link is a real visit", async () => {
    stubFetch({ tracker: ok([]) });

    await renderLoaded();

    expect(readRecentProjects()[0]).toMatchObject({
      projectId: "proj_1",
      jurisdictionCode: DEMO_PROJECT.jurisdictionCode,
    });
  });
});

describe("useProject", () => {
  it("throws outside a provider instead of handing back nothing", () => {
    expect(() => renderHook(useProject)).toThrow(/ProjectProvider/);
  });
});
