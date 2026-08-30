import { afterEach, describe, expect, it } from "vitest";

import { ApiError, fetchScript, fetchTracker } from "./client";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function respondWith(status: number, body: string): typeof fetch {
  return () => Promise.resolve(new Response(body, { status }));
}

describe("fetchScript", () => {
  it("maps a non-2xx response to a typed ApiError instead of a partial payload", async () => {
    globalThis.fetch = respondWith(500, "internal error");

    await expect(fetchScript("scr_1")).rejects.toBeInstanceOf(ApiError);
  });

  it("carries the response status and message on the thrown ApiError", async () => {
    globalThis.fetch = respondWith(500, "internal error");

    const failure = fetchScript("scr_1").catch((error: unknown) => error);

    await expect(failure).resolves.toMatchObject({
      status: 500,
      message: "internal error",
    });
  });
});

describe("fetchTracker", () => {
  it("maps a non-2xx response to a typed ApiError instead of a partial payload", async () => {
    globalThis.fetch = respondWith(404, "not found");

    await expect(fetchTracker("proj_1")).rejects.toBeInstanceOf(ApiError);
  });
});
