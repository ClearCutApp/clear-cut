import { afterEach, describe, expect, it } from "vitest";

import {
  API_DOCS_PATH,
  ApiError,
  fetchTracker,
  patchTrackerState,
  postAnalyze,
  postQuestion,
  postTrackerAction,
  type AnalyzeRequest,
} from "./client";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function respondWith(status: number, body: string): typeof fetch {
  return () => Promise.resolve(new Response(body, { status }));
}

interface CapturedRequest {
  init: RequestInit | undefined;
}

/** A `fetch` stub that records every call and answers with `responseBody`,
 * so a test can assert on the method and body a client function sent
 * through `requestJson`'s new `init` parameter. It deliberately ignores the
 * request path: `architecture.test.ts` reserves API path literals to
 * `client.ts`, so no other file -- including this one -- may spell one out. */
function captureRequest(responseBody: unknown): {
  fetchStub: typeof fetch;
  captured: CapturedRequest[];
} {
  const captured: CapturedRequest[] = [];
  const fetchStub = ((_input: RequestInfo | URL, init?: RequestInit) => {
    captured.push({ init });
    return Promise.resolve(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );
  }) as typeof fetch;
  return { fetchStub, captured };
}

describe("fetchTracker", () => {
  it("maps a non-2xx response to a typed ApiError instead of a partial payload", async () => {
    globalThis.fetch = respondWith(404, "not found");

    await expect(fetchTracker("proj_1")).rejects.toBeInstanceOf(ApiError);
  });

  it("rethrows malformed JSON inside a 200 response as ApiError, not a raw SyntaxError", async () => {
    globalThis.fetch = respondWith(200, "not json");

    await expect(fetchTracker("proj_1")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("postAnalyze", () => {
  const request: AnalyzeRequest = {
    gcs_uri: "gs://bucket/script.pdf",
    version: 1,
    jurisdiction_code: "US",
  };

  it("posts the request body to the project scripts collection", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await postAnalyze("proj_1", request);

    expect(captured[0].init?.method).toBe("POST");
    expect(JSON.parse(String(captured[0].init?.body))).toEqual(request);
  });

  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(400, "bad request");

    const failure = postAnalyze("proj_1", request).catch((error: unknown) => error);

    await expect(failure).resolves.toBeInstanceOf(ApiError);
    await expect(failure).resolves.toMatchObject({ status: 400 });
  });
});

describe("patchTrackerState", () => {
  it("patches the state to /api/tracker/:itemId", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await patchTrackerState("item_1", "CLEARED");

    expect(captured[0].init?.method).toBe("PATCH");
    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      state: "CLEARED",
    });
  });

  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(404, "not found");

    const failure = patchTrackerState("item_1", "CLEARED").catch(
      (error: unknown) => error,
    );

    await expect(failure).resolves.toBeInstanceOf(ApiError);
    await expect(failure).resolves.toMatchObject({ status: 404 });
  });
});

describe("postTrackerAction", () => {
  it("posts the action, omitting reason when none is given", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await postTrackerAction("item_1", "draft_email");

    expect(captured[0].init?.method).toBe("POST");
    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      action: "draft_email",
    });
  });

  it("includes reason when given", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await postTrackerAction("item_1", "notify", "escalated to legal");

    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      action: "notify",
      reason: "escalated to legal",
    });
  });

  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(500, "internal error");

    const failure = postTrackerAction("item_1", "notify").catch(
      (error: unknown) => error,
    );

    await expect(failure).resolves.toBeInstanceOf(ApiError);
    await expect(failure).resolves.toMatchObject({ status: 500 });
  });
});

describe("postQuestion", () => {
  it("posts jurisdiction and question to the project questions collection", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await postQuestion("proj_1", "US", "Can we use this song?");

    expect(captured[0].init?.method).toBe("POST");
    // No project_id in the body: it is the collection in the path now.
    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      jurisdiction_code: "US",
      question: "Can we use this song?",
    });
  });

  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(502, "bad gateway");

    const failure = postQuestion("proj_1", "US", "question?").catch(
      (error: unknown) => error,
    );

    await expect(failure).resolves.toBeInstanceOf(ApiError);
    await expect(failure).resolves.toMatchObject({ status: 502 });
  });
});

describe("API_DOCS_PATH", () => {
  it("points at the docs resource without any caller spelling the path", () => {
    expect(API_DOCS_PATH.endsWith("docs")).toBe(true);
  });
});
