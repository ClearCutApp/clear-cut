import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type { AnalyzeResponse, TrackerItem } from "../api/client";
import { DEMO_PROJECT } from "../app/demo";
import analyzeData from "../fixtures/analyze.json";
import trackerData from "../fixtures/tracker.json";
import { deferredResponse, stubFetch } from "../testing/fetchStub";
import { ProjectProvider, useProject } from "./ProjectContext";
import { readRecentProjects, rememberProject } from "./recentProjects";

const analyzeFixture = analyzeData as AnalyzeResponse;
const trackerFixture = trackerData as TrackerItem[];
const request = { gcs_uri: "gs://bucket/script.pdf", version: 1, jurisdiction_code: "US" };

function wrapperFor(projectId: string, initialAnalysis: AnalyzeResponse | null = null) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ProjectProvider projectId={projectId} initialAnalysis={initialAnalysis}>
        {children}
      </ProjectProvider>
    );
  };
}

function ok(body: unknown) {
  return { status: 200, body };
}

async function renderLoaded(initialAnalysis: AnalyzeResponse | null = null) {
  const hook = renderHook(useProject, { wrapper: wrapperFor("proj_1", initialAnalysis) });
  await waitFor(() => expect(hook.result.current.tracker).not.toBeNull());
  return hook;
}

describe("ProjectProvider tracker", () => {
  it("starts with no tracker and fills it from the mount GET", async () => {
    stubFetch({ tracker: ok(trackerFixture) });

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
    const { calls } = stubFetch({ tracker: [ok([]), ok(trackerFixture)] });
    const { result } = await renderLoaded();

    await act(() => result.current.refreshTracker());

    expect(result.current.tracker).toHaveLength(3);
    expect(calls.filter((call) => call.kind === "tracker")).toHaveLength(2);
  });
});

describe("ProjectProvider runAnalysis", () => {
  it("sets the analysis and the tracker from the response without a second GET", async () => {
    const { calls } = stubFetch({ tracker: ok([]), analyze: ok(analyzeFixture) });
    rememberProject("proj_1", "US");
    const { result } = await renderLoaded();

    let outcome;
    await act(async () => {
      outcome = await result.current.runAnalysis(request);
    });

    expect(outcome).toEqual({ ok: true, value: analyzeFixture });
    expect(result.current.analysis).toEqual(analyzeFixture);
    expect(result.current.tracker).toEqual(analyzeFixture.tracker_items);
    expect(result.current.jurisdictionCode).toBe(analyzeFixture.jurisdiction_code);
    expect(calls.filter((call) => call.kind === "tracker")).toHaveLength(1);
  });

  it("returns the 400 body as the message and leaves the session untouched", async () => {
    stubFetch({ tracker: ok([]), analyze: { status: 400, body: "gcs_uri is required" } });
    const { result } = await renderLoaded();

    let outcome;
    await act(async () => {
      outcome = await result.current.runAnalysis(request);
    });

    expect(outcome).toEqual({ ok: false, message: "gcs_uri is required" });
    expect(result.current.analysis).toBeNull();
    expect(result.current.tracker).toEqual([]);
  });
});

describe("ProjectProvider mutations", () => {
  it("changeState replaces exactly that row from the PATCH response, even when the response state differs", async () => {
    const patched = { ...trackerFixture[1], state: "CLEARED" as const, version: 2 };
    const { calls } = stubFetch({ tracker: ok(trackerFixture), patch: ok(patched) });
    const { result } = await renderLoaded();

    await act(() => result.current.changeState("EVT-002", "IN_PROGRESS"));

    expect(result.current.tracker?.[1]).toEqual(patched);
    expect(result.current.tracker?.[0]).toEqual(trackerFixture[0]);
    expect(result.current.tracker?.[2]).toEqual(trackerFixture[2]);
    expect(calls.find((call) => call.kind === "patch")?.body).toEqual({ state: "IN_PROGRESS" });
  });

  it("draftEmail replaces the row with the returned draft_email", async () => {
    const drafted = { ...trackerFixture[0], draft_email: "Dear Ferrari S.p.A., ..." };
    const { calls } = stubFetch({ tracker: ok(trackerFixture), action: ok(drafted) });
    const { result } = await renderLoaded();

    await act(() => result.current.draftEmail("EVT-001"));

    expect(result.current.tracker?.[0].draft_email).toBe("Dear Ferrari S.p.A., ...");
    expect(calls.find((call) => call.kind === "action")?.body).toEqual({ action: "draft_email" });
  });

  it("notify sends the bare action and leaves the row as the server returned it", async () => {
    const { calls } = stubFetch({ tracker: ok(trackerFixture), action: ok(trackerFixture[2]) });
    const { result } = await renderLoaded();

    await act(() => result.current.notify("EVT-003"));

    expect(result.current.tracker).toEqual(trackerFixture);
    expect(calls.find((call) => call.kind === "action")?.body).toEqual({ action: "notify" });
  });

  it("marks the item pending while its request is in flight and clears it after", async () => {
    const deferred = deferredResponse();
    stubFetch({ tracker: ok(trackerFixture), action: deferred.route });
    const { result } = await renderLoaded();

    let mutation: Promise<unknown> = Promise.resolve();
    act(() => {
      mutation = result.current.draftEmail("EVT-001");
    });

    await waitFor(() => expect(result.current.pendingItemIds.has("EVT-001")).toBe(true));
    deferred.resolve(ok(trackerFixture[0]));
    await act(() => mutation);
    expect(result.current.pendingItemIds.has("EVT-001")).toBe(false);
  });

  it("reports a failed mutation as a message, keeps the row and clears pending", async () => {
    stubFetch({ tracker: ok(trackerFixture), patch: { status: 404, body: "not found" } });
    const { result } = await renderLoaded();

    let outcome;
    await act(async () => {
      outcome = await result.current.changeState("EVT-001", "CLEARED");
    });

    expect(outcome).toEqual({ ok: false, message: "not found" });
    expect(result.current.tracker?.[0]).toEqual(trackerFixture[0]);
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
    stubFetch({ tracker: ok(trackerFixture) });
    const { result } = await renderLoaded();

    act(() => result.current.selectItem("EVT-002"));
    expect(result.current.selectedItemId).toBe("EVT-002");

    act(() => result.current.selectItem(null));
    expect(result.current.selectedItemId).toBeNull();
  });

  it("joins an item to its finding and a finding to its item through the session analysis", async () => {
    stubFetch({ tracker: ok(trackerFixture) });
    const { result } = await renderLoaded(analyzeFixture);

    expect(result.current.findingFor("EVT-003")?.contradicts).toBe("FACT-001");
    expect(result.current.itemFor("EVT-001")?.item_id).toBe("EVT-001");
    expect(result.current.findingFor("missing")).toBeNull();
    expect(result.current.itemFor("missing")).toBeNull();
  });

  it("finds no finding without an analysis in session", async () => {
    stubFetch({ tracker: ok(trackerFixture) });
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
