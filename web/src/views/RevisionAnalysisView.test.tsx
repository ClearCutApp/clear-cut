import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import { RevisionAnalysisView } from "./RevisionAnalysisView";

const state = vi.hoisted(() => ({
  runAnalysis: vi.fn(), listRevisions: vi.fn(), cancelAnalysis: vi.fn(),
  job: null as null | {analysis_id: string; state: string; stage: string},
}));
vi.mock("../api/client", () => ({ listRevisions: state.listRevisions, cancelAnalysis: state.cancelAnalysis }));
vi.mock("../state/ProjectContext", () => ({ useProject: () => ({projectId: "project", jurisdictionCode: "MX", runAnalysis: state.runAnalysis, job: state.job}) }));

beforeEach(() => {
  vi.clearAllMocks(); state.job = null;
  state.runAnalysis.mockResolvedValue({ok: false, message: "Queue unavailable"});
  state.listRevisions.mockResolvedValue({revisions: [{revision_id: "revision-4", draft_version: 4, created_at: "2026-09-06T00:00:00Z"}], next_before_version: null});
});

it("submits only the selected immutable revision and retains it after queue failure", async () => {
  render(<MemoryRouter><RevisionAnalysisView /></MemoryRouter>);
  await screen.findByRole("combobox", {name: "Saved revision"});
  fireEvent.click(screen.getByRole("button", {name: "Analyze revision"}));
  await waitFor(() => expect(state.runAnalysis).toHaveBeenCalledWith({revision_id: "revision-4", jurisdiction_code: "MX"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("Queue unavailable");
  expect(screen.getByRole("combobox")).toHaveValue("revision-4");
  expect(screen.getByRole("link", {name: "Open screenplay and save a revision"})).toHaveAttribute("href", "/projects/project/editor");
});

it("requires a saved revision before showing the primary analysis action", async () => {
  state.listRevisions.mockResolvedValue({revisions: [], next_before_version: null});
  render(<MemoryRouter><RevisionAnalysisView /></MemoryRouter>);
  await screen.findByText("Save your first revision in the screenplay editor before analyzing.");
  expect(screen.queryByRole("button", {name: "Analyze revision"})).not.toBeInTheDocument();
});

it("shows persisted stage progress and explicitly requests cancellation", async () => {
  state.job = {analysis_id: "analysis", state: "RUNNING", stage: "research"};
  state.cancelAnalysis.mockResolvedValue({state: "CANCELLED"});
  render(<MemoryRouter><RevisionAnalysisView /></MemoryRouter>);
  expect(screen.getByText(/Analysis in progress/)).toHaveTextContent("research");
  fireEvent.click(screen.getByRole("button", {name: "Cancel analysis"}));
  await waitFor(() => expect(state.cancelAnalysis).toHaveBeenCalledWith("project", "analysis"));
  expect(screen.getByText(/Research already submitted/)).toBeInTheDocument();
});
