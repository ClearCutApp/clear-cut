import { afterEach, describe, expect, it } from "vitest";

import {
  API_DOCS_PATH,
  ApiError,
  askProjectQuestion,
  createProject,
  createScript,
  createTrackerItemEmailDraft,
  createTrackerItemNotification,
  getAnalysis,
  getProject,
  getScript,
  getTrackerItem,
  listJurisdictions,
  listProjects,
  listScripts,
  listTrackerItems,
  updateTrackerItemState,
  type ScriptCreate,
} from "./client";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function respondWith(status: number, body: string): typeof fetch {
  return () => Promise.resolve(new Response(body, { status }));
}

interface CapturedRequest {
  url: string;
  init: RequestInit | undefined;
}

/**
 * A `fetch` stub that records every call and answers with `responseBody`.
 * The recorded url is asserted on by the segments a reader would name a
 * route by ("tracker-items", an id): `architecture.test.ts` reserves API
 * path literals to `client.ts`, so no test may spell a whole path out.
 */
function captureRequest(responseBody: unknown): {
  fetchStub: typeof fetch;
  captured: CapturedRequest[];
} {
  const captured: CapturedRequest[] = [];
  const fetchStub = ((input: RequestInfo | URL, init?: RequestInit) => {
    captured.push({ url: String(input), init });
    return Promise.resolve(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    );
  }) as typeof fetch;
  return { fetchStub, captured };
}

describe("listTrackerItems", () => {
  it("maps a non-2xx response to a typed ApiError instead of a partial payload", async () => {
    globalThis.fetch = respondWith(404, "not found");

    await expect(listTrackerItems("proj_1")).rejects.toBeInstanceOf(ApiError);
  });

  it("rethrows malformed JSON inside a 200 response as ApiError, not a raw SyntaxError", async () => {
    globalThis.fetch = respondWith(200, "not json");

    await expect(listTrackerItems("proj_1")).rejects.toBeInstanceOf(ApiError);
  });

  it("reads the project's own tracker collection", async () => {
    const { fetchStub, captured } = captureRequest([]);
    globalThis.fetch = fetchStub;

    await listTrackerItems("proj 1");

    expect(captured[0].url).toContain("tracker-items");
    expect(captured[0].url).toContain(encodeURIComponent("proj 1"));
  });
});

describe("getTrackerItem", () => {
  it("reads one item under its project", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await getTrackerItem("proj_1", "item_1");

    expect(captured[0].url).toContain("tracker-items");
    expect(captured[0].url.endsWith("item_1")).toBe(true);
  });
});

describe("listProjects", () => {
  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(500, "internal error");

    const failure = listProjects().catch((error: unknown) => error);

    await expect(failure).resolves.toMatchObject({ status: 500 });
  });
});

describe("createProject", () => {
  it("posts the title and jurisdiction the form collected", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await createProject({ title: "El Ultimo Verano", jurisdiction_code: "AR" });

    expect(captured[0].init?.method).toBe("POST");
    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      title: "El Ultimo Verano",
      jurisdiction_code: "AR",
    });
  });

  it("maps a rejected body to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(400, "title is required");

    const failure = createProject({ title: "", jurisdiction_code: "AR" }).catch(
      (error: unknown) => error,
    );

    await expect(failure).resolves.toMatchObject({
      status: 400,
      message: "title is required",
    });
  });
});

describe("getProject", () => {
  it("escapes a project id that is not url safe", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await getProject("proj/1");

    expect(captured[0].url.endsWith(encodeURIComponent("proj/1"))).toBe(true);
  });
});

describe("listJurisdictions", () => {
  it("reads the codes every jurisdiction field accepts", async () => {
    const { fetchStub, captured } = captureRequest([]);
    globalThis.fetch = fetchStub;

    await listJurisdictions();

    expect(captured[0].url).toContain("jurisdictions");
    expect(captured[0].init).toBeUndefined();
  });
});

describe("createScript", () => {
  const request: ScriptCreate = {
    gcs_uri: "gs://bucket/script.pdf",
    version: 1,
    jurisdiction_code: "US",
  };

  it("posts the request body to the project scripts collection", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await createScript("proj_1", request);

    expect(captured[0].init?.method).toBe("POST");
    expect(JSON.parse(String(captured[0].init?.body))).toEqual(request);
  });

  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(400, "bad request");

    const failure = createScript("proj_1", request).catch(
      (error: unknown) => error,
    );

    await expect(failure).resolves.toBeInstanceOf(ApiError);
    await expect(failure).resolves.toMatchObject({ status: 400 });
  });
});

describe("listScripts and getScript", () => {
  it("reads the version list without an id and one version with it", async () => {
    const { fetchStub, captured } = captureRequest([]);
    globalThis.fetch = fetchStub;

    await listScripts("proj_1");
    await getScript("proj_1", "scr_1");

    expect(captured[0].url.endsWith("scripts")).toBe(true);
    expect(captured[1].url.endsWith("scr_1")).toBe(true);
  });
});

describe("getAnalysis", () => {
  it("reads the queued job by the id the 202 handed back", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await getAnalysis("proj_1", "ana_1");

    expect(captured[0].url).toContain("analyses");
    expect(captured[0].url.endsWith("ana_1")).toBe(true);
  });
});

describe("updateTrackerItemState", () => {
  it("patches the state on the item under its project", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await updateTrackerItemState("proj_1", "item_1", "CLEARED");

    expect(captured[0].init?.method).toBe("PATCH");
    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      state: "CLEARED",
    });
  });

  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(404, "not found");

    const failure = updateTrackerItemState("proj_1", "item_1", "CLEARED").catch(
      (error: unknown) => error,
    );

    await expect(failure).resolves.toMatchObject({ status: 404 });
  });
});

describe("createTrackerItemEmailDraft", () => {
  it("posts to the item's own draft collection with no body", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await createTrackerItemEmailDraft("proj_1", "item_1");

    expect(captured[0].init?.method).toBe("POST");
    expect(captured[0].init?.body).toBeUndefined();
    expect(captured[0].url).toContain("email-drafts");
  });
});

describe("createTrackerItemNotification", () => {
  it("posts the reason the producer is being told", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await createTrackerItemNotification("proj_1", "item_1", "no answer in 14 days");

    expect(captured[0].url).toContain("notifications");
    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      reason: "no answer in 14 days",
    });
  });

  it("surfaces the server's own sentence when the reason is refused", async () => {
    globalThis.fetch = respondWith(400, "reason is required");

    const failure = createTrackerItemNotification("proj_1", "item_1", " ").catch(
      (error: unknown) => error,
    );

    await expect(failure).resolves.toMatchObject({
      status: 400,
      message: "reason is required",
    });
  });
});

describe("askProjectQuestion", () => {
  it("posts jurisdiction and question to the project questions collection", async () => {
    const { fetchStub, captured } = captureRequest({});
    globalThis.fetch = fetchStub;

    await askProjectQuestion("proj_1", "US", "Can we use this song?");

    expect(captured[0].init?.method).toBe("POST");
    // No project_id in the body: it is the collection in the path now.
    expect(JSON.parse(String(captured[0].init?.body))).toEqual({
      jurisdiction_code: "US",
      question: "Can we use this song?",
    });
  });

  it("maps a non-2xx response to a typed ApiError carrying the status", async () => {
    globalThis.fetch = respondWith(502, "bad gateway");

    const failure = askProjectQuestion("proj_1", "US", "question?").catch(
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
