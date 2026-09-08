import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { ServerModeProvider } from "./state/ServerModeContext";
import { stubFetch } from "./testing/fetchStub";

function renderAt(path: string, mode = "mock") {
  stubFetch({
    health: { status: 200, body: { mode } },
    tracker: { status: 200, body: [] },
  });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ServerModeProvider>
        <App />
      </ServerModeProvider>
    </MemoryRouter>,
  );
}

describe("App routes", () => {
  it("opens the public landing with an account action", () => {
    renderAt("/");

    expect(screen.getByRole("link", { name: "Start your workspace" })).toHaveAttribute("href", "/signup");
  });

  it("opens a project on its overview, under the project header", async () => {
    renderAt("/projects/demo%20x");

    expect(await screen.findByRole("heading", { name: "demo x" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });

  it("routes the analyze, script and ask views under a project", async () => {
    const { unmount: unmountAnalyze } = renderAt("/projects/p/analyze");
    expect(await screen.findByRole("heading", { name: "Run analysis" })).toBeInTheDocument();
    unmountAnalyze();

    const { unmount: unmountScript } = renderAt("/projects/p/script");
    expect(await screen.findByRole("heading", { name: "Script" })).toBeInTheDocument();
    unmountScript();

    renderAt("/projects/p/ask");
    expect(await screen.findByRole("heading", { name: "Ask ClearCut" })).toBeInTheDocument();
  });

  it("answers an unknown path with the not-found view", async () => {
    renderAt("/nowhere/at/all");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });

  it("shows the demo banner on the project workspace when the server is in mock mode", async () => {
    renderAt("/projects", "mock");

    expect(await screen.findByTestId("mode-banner")).toBeInTheDocument();
  });
});
