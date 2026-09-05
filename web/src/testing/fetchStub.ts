/**
 * A `fetch` stand-in for tests. It tells requests apart by method and by
 * the bare collection words a route is named after, never by a whole path:
 * `architecture.test.ts` reserves API path literals to `client.ts`, so no
 * test may spell one out either. Every call is recorded so a test can
 * assert on what a handler sent.
 *
 * A collection and one of its members are separate kinds ("tracker" and
 * "tracker-item", "scripts" and "script"), because a test that stubs the
 * list must not accidentally answer a read of one row.
 */
export type RouteKind =
  | "health"
  | "jurisdictions"
  | "projects"
  | "project"
  | "create-project"
  | "scripts"
  | "script"
  | "create-script"
  | "analysis"
  | "tracker"
  | "tracker-item"
  | "patch"
  | "email-draft"
  | "notification"
  | "question";

export interface StubResponse {
  status: number;
  /** A string is sent as-is; anything else is JSON-encoded. */
  body: unknown;
}

export type StubRoute =
  | StubResponse
  | StubResponse[]
  | ((init?: RequestInit) => Promise<Response>);

export interface RecordedCall {
  kind: RouteKind;
  method: string;
  body: unknown;
}

export interface FetchStub {
  calls: RecordedCall[];
  restore: () => void;
}

/** The path segment following `collection`, or "" when the collection is
 * the last segment -- which is what tells a list read from a member read. */
function segmentAfter(url: string, collection: string): string {
  const segments = url.split("/").filter(Boolean);
  const index = segments.indexOf(collection);
  return index === -1 ? "" : (segments[index + 1] ?? "");
}

function classify(input: RequestInfo | URL, init?: RequestInit): RouteKind {
  const method = (init?.method ?? "GET").toUpperCase();
  const url = String(input);
  if (method === "PATCH") {
    return "patch";
  }
  if (method === "POST") {
    if (url.includes("email-drafts")) {
      return "email-draft";
    }
    if (url.includes("notifications")) {
      return "notification";
    }
    if (url.includes("questions")) {
      return "question";
    }
    return url.includes("scripts") ? "create-script" : "create-project";
  }
  if (url.includes("health")) {
    return "health";
  }
  if (url.includes("jurisdictions")) {
    return "jurisdictions";
  }
  if (url.includes("analyses")) {
    return "analysis";
  }
  if (url.includes("tracker-items")) {
    return segmentAfter(url, "tracker-items") === "" ? "tracker" : "tracker-item";
  }
  if (url.includes("scripts")) {
    return segmentAfter(url, "scripts") === "" ? "scripts" : "script";
  }
  return segmentAfter(url, "projects") === "" ? "projects" : "project";
}

function parseBody(init?: RequestInit): unknown {
  if (typeof init?.body !== "string") {
    return undefined;
  }
  try {
    return JSON.parse(init.body);
  } catch {
    return init.body;
  }
}

function toResponse({ status, body }: StubResponse): Response {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return new Response(text, { status });
}

/** Sequences answer in order and their last entry repeats. */
function answer(route: StubRoute, init?: RequestInit): Promise<Response> {
  if (typeof route === "function") {
    return route(init);
  }
  if (Array.isArray(route)) {
    const next = route.length > 1 ? route.shift() : route[0];
    return Promise.resolve(toResponse(next as StubResponse));
  }
  return Promise.resolve(toResponse(route));
}

/**
 * Installs the stub on `globalThis.fetch`. `setupTests.ts` restores the
 * real `fetch` after every test; `restore` exists for tests that swap
 * stubs midway. A kind with no route answers 404 so the gap is visible.
 */
export function stubFetch(routes: Partial<Record<RouteKind, StubRoute>>): FetchStub {
  const original = globalThis.fetch;
  const calls: RecordedCall[] = [];
  const queues: Partial<Record<RouteKind, StubRoute>> = {};
  for (const [kind, route] of Object.entries(routes)) {
    queues[kind as RouteKind] = Array.isArray(route) ? [...route] : route;
  }
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const kind = classify(input, init);
    calls.push({ kind, method: (init?.method ?? "GET").toUpperCase(), body: parseBody(init) });
    const route = queues[kind];
    if (route === undefined) {
      return Promise.resolve(new Response(`no stub for ${kind}`, { status: 404 }));
    }
    return answer(route, init);
  }) as typeof fetch;
  return {
    calls,
    restore: () => {
      globalThis.fetch = original;
    },
  };
}

/** A response a test resolves by hand, for asserting in-flight state. */
export function deferredResponse(): {
  route: (init?: RequestInit) => Promise<Response>;
  resolve: (response: StubResponse) => void;
} {
  let settle: (response: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    settle = resolve;
  });
  return {
    route: () => pending,
    resolve: (response) => settle(toResponse(response)),
  };
}
