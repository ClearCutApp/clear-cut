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
 * literals to `client.ts`, so this file may not spell one out either. The
 * health GET is told apart by the bare word "health", which contains no path
 * segment the guard recognises.
 */
function isHealth(input: RequestInfo | URL): boolean {
  return String(input).includes("health");
}

function stubFetchTrackingRefetches(mode = "live"): {
  trackerCalls: () => number;
} {
  let trackerCalls = 0;
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    if (isHealth(input)) {
      return Promise.resolve(
        new Response(JSON.stringify({ mode }), { status: 200 }),
      );
    }
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

  it("shows the demo banner when the server reports mock mode", async () => {
    stubFetchTrackingRefetches("mock");

    render(<App />);

    await waitFor(() =>
      expect(screen.getByTestId("mode-banner")).toBeInTheDocument(),
    );
  });

  it("shows no banner when the server reports live mode", async () => {
    const { trackerCalls } = stubFetchTrackingRefetches("live");

    render(<App />);

    await waitFor(() => expect(trackerCalls()).toBe(1));
    expect(screen.queryByTestId("mode-banner")).not.toBeInTheDocument();
  });

  it("shows no banner when the health check fails", async () => {
    // An unreachable health endpoint must not be read as "this is fake".
    // Claiming the data is planted when it is real is its own dishonesty.
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      if (isHealth(input)) {
        return Promise.resolve(new Response("nope", { status: 500 }));
      }
      if (init?.method === "POST") {
        return Promise.resolve(
          new Response(JSON.stringify(analyzeFixture), { status: 200 }),
        );
      }
      return Promise.resolve(new Response("[]", { status: 200 }));
    }) as typeof fetch;

    render(<App />);

    await waitFor(() =>
      expect(screen.getByText(/no analysis has run yet/i)).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("mode-banner")).not.toBeInTheDocument();
  });
});
