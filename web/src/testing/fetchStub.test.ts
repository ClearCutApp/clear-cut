import { describe, expect, it } from "vitest";

import {
  askProjectQuestion,
  createProject,
  createScript,
  createTrackerItemEmailDraft,
  createTrackerItemNotification,
  getAnalysis,
  getHealth,
  getProject,
  getScript,
  getTrackerItem,
  listJurisdictions,
  listProjects,
  listScripts,
  listTrackerItems,
  updateTrackerItemState,
} from "../api/client";
import { deferredResponse, stubFetch } from "./fetchStub";

const OK = { status: 200, body: {} };

describe("stubFetch", () => {
  it("routes each client function to its own kind, collection apart from member", async () => {
    const { calls } = stubFetch({
      health: { status: 200, body: { mode: "mock" } },
      jurisdictions: { status: 200, body: [] },
      projects: { status: 200, body: [] },
      project: OK,
      "create-project": OK,
      scripts: { status: 200, body: [] },
      script: OK,
      "create-script": OK,
      analysis: OK,
      tracker: { status: 200, body: [] },
      "tracker-item": OK,
      patch: OK,
      "email-draft": OK,
      notification: OK,
      question: OK,
    });

    await getHealth();
    await listJurisdictions();
    await listProjects();
    await getProject("p");
    await createProject({ title: "t", jurisdiction_code: "AR" });
    await listScripts("p");
    await getScript("p", "s");
    await createScript("p", { gcs_uri: "gs://b/o", version: 1, jurisdiction_code: "US" });
    await getAnalysis("p", "a");
    await listTrackerItems("p");
    await getTrackerItem("p", "i");
    await updateTrackerItemState("p", "i", "CLEARED");
    await createTrackerItemEmailDraft("p", "i");
    await createTrackerItemNotification("p", "i", "no answer");
    await askProjectQuestion("p", "US", "why?");

    expect(calls.map((call) => call.kind)).toEqual([
      "health",
      "jurisdictions",
      "projects",
      "project",
      "create-project",
      "scripts",
      "script",
      "create-script",
      "analysis",
      "tracker",
      "tracker-item",
      "patch",
      "email-draft",
      "notification",
      "question",
    ]);
    expect(calls[11].body).toEqual({ state: "CLEARED" });
  });

  it("answers a sequence in order and repeats its last entry", async () => {
    stubFetch({
      tracker: [
        { status: 200, body: [] },
        { status: 200, body: [{ item_id: "x" }] },
      ],
    });

    await expect(listTrackerItems("p")).resolves.toEqual([]);
    await expect(listTrackerItems("p")).resolves.toEqual([{ item_id: "x" }]);
    await expect(listTrackerItems("p")).resolves.toEqual([{ item_id: "x" }]);
  });

  it("answers 404 for a kind with no route so the gap is visible", async () => {
    stubFetch({});

    await expect(listTrackerItems("p")).rejects.toMatchObject({ status: 404 });
  });

  it("holds a deferred response until the test resolves it", async () => {
    const deferred = deferredResponse();
    stubFetch({ tracker: deferred.route });
    let settled = false;
    const request = listTrackerItems("p").then((items) => {
      settled = true;
      return items;
    });

    await Promise.resolve();
    expect(settled).toBe(false);

    deferred.resolve({ status: 200, body: [] });
    await expect(request).resolves.toEqual([]);
  });

  it("restores the real fetch on demand", () => {
    const original = globalThis.fetch;
    const { restore } = stubFetch({});

    expect(globalThis.fetch).not.toBe(original);
    restore();
    expect(globalThis.fetch).toBe(original);
  });
});
