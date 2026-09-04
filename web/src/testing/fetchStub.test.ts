import { describe, expect, it } from "vitest";

import {
  fetchHealth,
  fetchTracker,
  patchTrackerState,
  postAnalyze,
  postQuestion,
  postTrackerAction,
} from "../api/client";
import { deferredResponse, stubFetch } from "./fetchStub";

describe("stubFetch", () => {
  it("routes each client function to its kind by method and body, never by path", async () => {
    const { calls } = stubFetch({
      health: { status: 200, body: { mode: "mock" } },
      tracker: { status: 200, body: [] },
      analyze: { status: 200, body: {} },
      patch: { status: 200, body: {} },
      action: { status: 200, body: {} },
      question: { status: 200, body: {} },
    });

    await fetchHealth();
    await fetchTracker("p");
    await postAnalyze("p", { gcs_uri: "gs://b/o", version: 1, jurisdiction_code: "US" });
    await patchTrackerState("i", "CLEARED");
    await postTrackerAction("i", "notify");
    await postQuestion("p", "US", "why?");

    expect(calls.map((call) => call.kind)).toEqual([
      "health",
      "tracker",
      "analyze",
      "patch",
      "action",
      "question",
    ]);
    expect(calls[3].body).toEqual({ state: "CLEARED" });
  });

  it("answers a sequence in order and repeats its last entry", async () => {
    stubFetch({
      tracker: [
        { status: 200, body: [] },
        { status: 200, body: [{ item_id: "x" }] },
      ],
    });

    await expect(fetchTracker("p")).resolves.toEqual([]);
    await expect(fetchTracker("p")).resolves.toEqual([{ item_id: "x" }]);
    await expect(fetchTracker("p")).resolves.toEqual([{ item_id: "x" }]);
  });

  it("answers 404 for a kind with no route so the gap is visible", async () => {
    stubFetch({});

    await expect(fetchTracker("p")).rejects.toMatchObject({ status: 404 });
  });

  it("holds a deferred response until the test resolves it", async () => {
    const deferred = deferredResponse();
    stubFetch({ tracker: deferred.route });
    let settled = false;
    const request = fetchTracker("p").then((items) => {
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
