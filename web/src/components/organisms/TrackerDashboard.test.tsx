import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { TrackerItem } from "../../api/client";
import trackerFixture from "../../fixtures/tracker.json";
import { TrackerDashboard } from "./TrackerDashboard";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function respondWith(status: number, body: string): typeof fetch {
  return (() => Promise.resolve(new Response(body, { status }))) as typeof fetch;
}

interface CapturedRequest {
  init: RequestInit | undefined;
}

/** A `fetch` stub that answers the mount `GET` (no `init`) with `listBody`
 * and every mutation call (`PATCH` or `POST`, which always carries `init`)
 * with `mutationBody`, while recording every call so a test can assert on
 * the method and body a handler actually sent. It never inspects the
 * request path, matching `client.test.ts`'s pattern -- `architecture.test.ts`
 * reserves API path literals to `client.ts` alone. */
function routedFetch(
  calls: CapturedRequest[],
  listBody: unknown,
  mutationBody: unknown,
): typeof fetch {
  return ((_input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ init });
    const body = init === undefined ? listBody : mutationBody;
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  }) as typeof fetch;
}

describe("TrackerDashboard", () => {
  it("fetches the tracker on mount and renders each item's state", async () => {
    globalThis.fetch = respondWith(200, JSON.stringify(trackerFixture));

    render(<TrackerDashboard projectId="demo-project" refreshKey={0} />);

    await waitFor(() =>
      expect(screen.getAllByTestId("tracker-row")).toHaveLength(3),
    );
    expect(screen.getByText(/legal@ferrari\.example/)).toBeInTheDocument();
  });

  it("renders a visible error instead of a blank panel when the fetch fails", async () => {
    globalThis.fetch = respondWith(500, "internal error");

    render(<TrackerDashboard projectId="demo-project" refreshKey={0} />);

    await waitFor(() =>
      expect(screen.getByText("internal error")).toBeInTheDocument(),
    );
  });

  it("shows a worded empty state before any analysis has run", async () => {
    globalThis.fetch = respondWith(200, "[]");

    render(<TrackerDashboard projectId="demo-project" refreshKey={0} />);

    await waitFor(() =>
      expect(
        screen.getByText(/no analysis has run yet/i),
      ).toBeInTheDocument(),
    );
  });

  it("re-fetches when refreshKey changes", async () => {
    let calls = 0;
    globalThis.fetch = (() => {
      calls += 1;
      return Promise.resolve(
        new Response(JSON.stringify(trackerFixture), { status: 200 }),
      );
    }) as typeof fetch;

    const { rerender } = render(
      <TrackerDashboard projectId="demo-project" refreshKey={0} />,
    );
    await waitFor(() => expect(calls).toBe(1));

    rerender(<TrackerDashboard projectId="demo-project" refreshKey={1} />);
    await waitFor(() => expect(calls).toBe(2));
  });

  it("replaces the row's displayed state with the PATCH response, not the option the user picked", async () => {
    const calls: CapturedRequest[] = [];
    const patchedItem: TrackerItem = {
      ...(trackerFixture[0] as TrackerItem),
      state: "CLEARED",
      version: 2,
    };
    globalThis.fetch = routedFetch(calls, trackerFixture, patchedItem);

    render(<TrackerDashboard projectId="demo-project" refreshKey={0} />);
    await waitFor(() =>
      expect(screen.getAllByTestId("tracker-row")).toHaveLength(3),
    );

    fireEvent.change(screen.getAllByLabelText(/^state$/i)[0], {
      target: { value: "IN_PROGRESS" },
    });

    // The server's response ("CLEARED") differs on purpose from the option
    // the user picked ("IN_PROGRESS"), so this only passes if the row is
    // replaced from the PATCH response rather than the locally selected
    // value -- and it fails if the mutation never lands at all.
    await waitFor(() =>
      expect(screen.getAllByTestId("state-badge")[0]).toHaveTextContent(
        "CLEARED",
      ),
    );

    const mutationCall = calls.find((call) => call.init?.method === "PATCH");
    expect(mutationCall).toBeDefined();
    expect(JSON.parse(String(mutationCall?.init?.body))).toEqual({
      state: "IN_PROGRESS",
    });
  });

  it("shows the returned draft email text after the Draft email action, from the POST response", async () => {
    const calls: CapturedRequest[] = [];
    const draftedItem: TrackerItem = {
      ...(trackerFixture[0] as TrackerItem),
      draft_email:
        "Dear Ferrari S.p.A., we are writing to request licensing terms.",
    };
    globalThis.fetch = routedFetch(calls, trackerFixture, draftedItem);

    render(<TrackerDashboard projectId="demo-project" refreshKey={0} />);
    await waitFor(() =>
      expect(screen.getAllByTestId("tracker-row")).toHaveLength(3),
    );
    expect(screen.queryByTestId("draft-email-text")).toBeNull();

    fireEvent.click(screen.getAllByRole("button", { name: /draft email/i })[0]);

    await waitFor(() =>
      expect(screen.getByTestId("draft-email-text")).toHaveTextContent(
        draftedItem.draft_email as string,
      ),
    );

    const mutationCall = calls.find((call) => call.init?.method === "POST");
    expect(mutationCall).toBeDefined();
    expect(JSON.parse(String(mutationCall?.init?.body))).toEqual({
      action: "draft_email",
    });
  });

  it("disables that row's actions while the draft email request is in flight, then re-enables them", async () => {
    let resolveMutation: (response: Response) => void = () => {};
    const mutationPromise = new Promise<Response>((resolve) => {
      resolveMutation = resolve;
    });
    globalThis.fetch = ((_input: RequestInfo | URL, init?: RequestInit) =>
      init === undefined
        ? Promise.resolve(
            new Response(JSON.stringify(trackerFixture), { status: 200 }),
          )
        : mutationPromise) as typeof fetch;

    render(<TrackerDashboard projectId="demo-project" refreshKey={0} />);
    await waitFor(() =>
      expect(screen.getAllByTestId("tracker-row")).toHaveLength(3),
    );

    fireEvent.click(screen.getAllByRole("button", { name: /draft email/i })[0]);

    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: /draft email/i })[0]).toBeDisabled(),
    );
    expect(screen.getAllByRole("button", { name: /notify/i })[0]).toBeDisabled();

    resolveMutation(
      new Response(
        JSON.stringify({
          ...(trackerFixture[0] as TrackerItem),
          draft_email: "Dear Ferrari S.p.A., ...",
        }),
        { status: 200 },
      ),
    );

    await waitFor(() =>
      expect(
        screen.getAllByRole("button", { name: /draft email/i })[0],
      ).toBeEnabled(),
    );
  });
});
