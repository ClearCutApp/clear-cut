import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { stubFetch } from "../testing/fetchStub";
import { ServerModeProvider, useServerMode } from "./ServerModeContext";

function ModeProbe() {
  const mode = useServerMode();
  return <output>{mode ?? "unknown"}</output>;
}

describe("ServerModeProvider", () => {
  it("exposes the mode the health endpoint reports", async () => {
    stubFetch({ health: { status: 200, body: { mode: "mock" } } });

    render(
      <ServerModeProvider>
        <ModeProbe />
      </ServerModeProvider>,
    );

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("mock"));
  });

  it("asks the health endpoint once, not once per consumer", async () => {
    const { calls } = stubFetch({ health: { status: 200, body: { mode: "live" } } });

    render(
      <ServerModeProvider>
        <ModeProbe />
        <ModeProbe />
      </ServerModeProvider>,
    );

    await waitFor(() =>
      expect(screen.getAllByRole("status")[1]).toHaveTextContent("live"),
    );
    expect(calls.filter((call) => call.kind === "health")).toHaveLength(1);
  });

  it("leaves the mode unknown when the health check fails", async () => {
    const { calls } = stubFetch({ health: { status: 500, body: "nope" } });

    render(
      <ServerModeProvider>
        <ModeProbe />
      </ServerModeProvider>,
    );

    await waitFor(() => expect(calls).toHaveLength(1));
    expect(screen.getByRole("status")).toHaveTextContent("unknown");
  });

  it("is unknown outside any provider", () => {
    render(<ModeProbe />);

    expect(screen.getByRole("status")).toHaveTextContent("unknown");
  });
});
