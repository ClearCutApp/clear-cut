import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import analyzeFixture from "./fixtures/analyze.json";
import trackerFixture from "./fixtures/tracker.json";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

/**
 * Distinguishes the analyze POST from a tracker GET by `init.method`
 * rather than the request path -- `architecture.test.ts` reserves API path
 * literals to `client.ts`, so this file may not spell one out either.
 */
function stubFetchTrackingRefetches(): { trackerCalls: () => number } {
  let trackerCalls = 0;
  globalThis.fetch = ((_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      return Promise.resolve(
        new Response(JSON.stringify(analyzeFixture), { status: 200 }),
      );
    }
    trackerCalls += 1;
    const body = trackerCalls === 1 ? "[]" : JSON.stringify(trackerFixture);
    return Promise.resolve(new Response(body, { status: 200 }));
  }) as typeof fetch;
  return { trackerCalls: () => trackerCalls };
}

describe("App", () => {
  it("bumps trackerRefresh after a successful analyze, so the tracker re-fetches", async () => {
    const { trackerCalls } = stubFetchTrackingRefetches();

    render(<App />);

    await waitFor(() => expect(trackerCalls()).toBe(1));
    expect(screen.getByText(/no analysis has run yet/i)).toBeInTheDocument();

    screen.getByRole("button", { name: /analyze/i }).click();

    await waitFor(() => expect(trackerCalls()).toBe(2));
    await waitFor(() =>
      expect(screen.getAllByTestId("tracker-row")).toHaveLength(3),
    );
  });
});
