import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../../api/client";
import { LocalResearchPanel } from "./LocalResearchPanel";

afterEach(() => vi.restoreAllMocks());
const settings: api.ProjectSettings = { project_id: "one", title: "Film", jurisdiction_code: "AR", version: 2, locations: [{ country: "AR", location: "Saved plaza" }] };
const result: api.LocalResearchRecord = { research_id: "research", project_id: "one", created_at: "2026-09-06", settings_version: 2, location: settings.locations[0], question: "Close this road?", text: "Evidence", citations: [{ uri: "https://buenosaires.gob.ar/permits", title: "Official permits", snippet: "Conditions must be checked." }], status: "evidence_found", human_clearance: false, provider: "Parallel Search" };

it("researches saved settings explicitly and preserves the question on conflict", async () => {
  vi.spyOn(api, "getProjectSettings").mockResolvedValue(settings);
  vi.spyOn(api, "listLocalResearch").mockResolvedValue({ configured: true, research: [] });
  const submit = vi.spyOn(api, "researchProductionLocation").mockRejectedValue(new api.ApiError(409, "changed"));
  render(<LocalResearchPanel projectId="one" savedVersion={2} editable />);
  fireEvent.change(await screen.findByLabelText("Local requirements question"), { target: { value: "Close this road?" } });
  expect(submit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Research and save evidence" }));
  await screen.findByRole("alert");
  expect(submit).toHaveBeenCalledWith("one", 2, 0, "Close this road?");
  expect(screen.getByLabelText("Local requirements question")).toHaveValue("Close this road?");
});

it("ignores a research result after the user switches projects", async () => {
  vi.spyOn(api, "getProjectSettings").mockResolvedValue(settings);
  vi.spyOn(api, "listLocalResearch").mockResolvedValue({ configured: true, research: [] });
  let resolve!: (value: api.LocalResearchRecord) => void;
  vi.spyOn(api, "researchProductionLocation").mockReturnValue(new Promise(done => { resolve = done; }));
  const view = render(<LocalResearchPanel projectId="one" savedVersion={2} editable />);
  fireEvent.change(await screen.findByLabelText("Local requirements question"), { target: { value: "Close this road?" } });
  fireEvent.click(screen.getByRole("button", { name: "Research and save evidence" }));
  view.rerender(<LocalResearchPanel projectId="two" savedVersion={2} editable />);
  await act(async () => resolve(result));
  expect(screen.queryByText("Conditions must be checked.")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Local requirements question")).toHaveValue("");
});
