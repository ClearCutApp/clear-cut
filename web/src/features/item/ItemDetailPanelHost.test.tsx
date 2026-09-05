import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AnalyzeResponse, TrackerItem } from "../../api/client";
import { DEMO_PROJECT } from "../../app/demo";
import analyzeData from "../../fixtures/analyze.json";
import trackerData from "../../fixtures/tracker.json";
import { stubFetch } from "../../testing/fetchStub";
import { renderWithProject } from "../../testing/renderWithProject";
import { jurisdictionName } from "../../theme/jurisdictions";
import { ItemDetailPanelHost } from "./ItemDetailPanelHost";

const analyzeFixture = analyzeData as AnalyzeResponse;
const trackerFixture = trackerData as TrackerItem[];

function ok(body: unknown) {
  return { status: 200, body };
}

describe("ItemDetailPanelHost", () => {
  it("renders nothing while no item is selected", () => {
    stubFetch({ tracker: ok(trackerFixture) });

    renderWithProject(<ItemDetailPanelHost />);

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("names the selected item and closes on request", async () => {
    stubFetch({ tracker: ok(trackerFixture) });

    renderWithProject(<ItemDetailPanelHost />, { selectedItemId: "EVT-002" });

    await screen.findByText("sync@warnerchappell.example");
    expect(screen.getByRole("dialog", { name: "EVT-002" })).toHaveClass("item-panel");

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows the finding and tracker facts of the selected item with the analysis in session", async () => {
    stubFetch({ tracker: ok(trackerFixture) });

    renderWithProject(<ItemDetailPanelHost />, {
      analysis: analyzeFixture,
      selectedItemId: "EVT-001",
    });

    expect(await screen.findByText("Ferrari Testarossa")).toBeInTheDocument();
    expect(screen.getByTestId("risk-badge")).toHaveTextContent("MEDIUM");
    expect(screen.getByText(jurisdictionName(DEMO_PROJECT.jurisdictionCode))).toBeInTheDocument();
    expect(screen.getByText("legal@ferrari.example")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ley de Marcas y Designaciones 22.362" }),
    ).toBeInTheDocument();
  });

  it("says the finding is unavailable without an analysis in session", async () => {
    stubFetch({ tracker: ok(trackerFixture) });

    renderWithProject(<ItemDetailPanelHost />, { selectedItemId: "EVT-001" });

    expect(await screen.findByText(/Finding details are available/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run analysis" })).toHaveAttribute(
      "href",
      "/projects/demo-project/analyze",
    );
    expect(screen.queryByTestId("risk-badge")).toBeNull();
  });

  it("replaces the row from the PATCH response when the state changes", async () => {
    const patched = { ...trackerFixture[0], state: "IN_PROGRESS" as const, version: 2 };
    const { calls } = stubFetch({ tracker: ok(trackerFixture), patch: ok(patched) });

    renderWithProject(<ItemDetailPanelHost />, {
      analysis: analyzeFixture,
      selectedItemId: "EVT-001",
    });

    fireEvent.change(await screen.findByLabelText("State"), {
      target: { value: "IN_PROGRESS" },
    });

    await waitFor(() =>
      expect(screen.getByTestId("state-badge")).toHaveTextContent("IN_PROGRESS"),
    );
    expect(screen.getByText(/Version 2/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(calls.find((call) => call.kind === "patch")?.body).toEqual({ state: "IN_PROGRESS" });
  });

  it("shows a PATCH failure inside the panel and keeps the row as it was", async () => {
    stubFetch({ tracker: ok(trackerFixture), patch: { status: 404, body: "not found" } });

    renderWithProject(<ItemDetailPanelHost />, {
      analysis: analyzeFixture,
      selectedItemId: "EVT-001",
    });

    fireEvent.change(await screen.findByLabelText("State"), { target: { value: "CLEARED" } });

    const dialog = screen.getByRole("dialog");
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("not found");
    expect(screen.getByTestId("state-badge")).toHaveTextContent("BLOCKED");
    expect(screen.getByLabelText("State")).toHaveValue("BLOCKED");
    expect(screen.getByText(/Version 1/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("State")).toBeEnabled());
  });

  it("shows the returned draft email after Draft email", async () => {
    const drafted = {
      ...trackerFixture[0],
      draft_email: "Subject: Rights clearance request -- Trademark Clearance Form",
    };
    const { calls } = stubFetch({ tracker: ok(trackerFixture), action: ok(drafted) });

    renderWithProject(<ItemDetailPanelHost />, {
      analysis: analyzeFixture,
      selectedItemId: "EVT-001",
    });

    fireEvent.click(await screen.findByRole("button", { name: "Draft email" }));

    const draft = await screen.findByText(/Subject: Rights clearance request/);
    expect(draft.tagName).toBe("PRE");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(calls.find((call) => call.kind === "action")?.body).toEqual({ action: "draft_email" });
  });

  it("leaves the row unchanged and shows no error after Notify", async () => {
    const { calls } = stubFetch({ tracker: ok(trackerFixture), action: ok(trackerFixture[2]) });

    renderWithProject(<ItemDetailPanelHost />, { selectedItemId: "EVT-003" });

    fireEvent.click(await screen.findByRole("button", { name: "Notify" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Notify" })).toBeEnabled());
    expect(calls.find((call) => call.kind === "action")?.body).toEqual({ action: "notify" });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("no contact on file")).toBeInTheDocument();
    expect(screen.getByText(/Version 1/)).toBeInTheDocument();
  });

  it("shows the tracker failure inside the panel when the mount GET fails", async () => {
    stubFetch({ tracker: { status: 500, body: "internal error" } });

    renderWithProject(<ItemDetailPanelHost />, { selectedItemId: "EVT-001" });

    const dialog = await screen.findByRole("dialog", { name: "EVT-001" });
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("internal error");
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    expect(screen.queryByLabelText("State")).toBeNull();
  });
});
