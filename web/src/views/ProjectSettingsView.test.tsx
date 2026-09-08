import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { ProjectSettingsView } from "./ProjectSettingsView";

let projectId = "one";
vi.mock("../state/ProjectContext", () => ({ useProject: () => ({ projectId }) }));
vi.mock("../state/ServerModeContext", () => ({ useServerMode: () => "live" }));
beforeEach(() => { vi.spyOn(api, "listLocalResearch").mockResolvedValue({ configured: true, research: [] }); });
afterEach(() => { vi.restoreAllMocks(); projectId = "one"; });
const settings: api.ProjectSettings = { project_id: "one", title: "Original title", jurisdiction_code: "AR", version: 2, locations: [] };
const access: api.ProjectMembers = { organization_id: "org", version: 1, can_manage: false, can_edit: true, members: [] };

it("preserves edited locations and title after an expected-version conflict", async () => {
  vi.spyOn(api, "getProjectSettings").mockResolvedValue(settings);
  vi.spyOn(api, "getProjectMembers").mockResolvedValue(access);
  const save = vi.spyOn(api, "saveProjectSettings").mockRejectedValue(new api.ApiError(409, "changed"));
  render(<ProjectSettingsView />);
  fireEvent.change(await screen.findByLabelText("Project title"), { target: { value: "Local work" } });
  fireEvent.click(screen.getByRole("button", { name: "Add location" }));
  fireEvent.change(screen.getByLabelText("Location"), { target: { value: "Buenos Aires public plaza" } });
  fireEvent.click(screen.getByRole("button", { name: "Save production settings" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Project title")).toHaveValue("Local work");
  expect(screen.getByLabelText("Location")).toHaveValue("Buenos Aires public plaza");
  expect(save).toHaveBeenCalledWith("one", expect.objectContaining({ version: 2, locations: [{ country: "AR", location: "Buenos Aires public plaza" }] }));
});

it("does not expose settings from a previous project after a late response", async () => {
  let resolve!: (value: api.ProjectSettings) => void;
  vi.spyOn(api, "getProjectSettings").mockReturnValueOnce(new Promise(done => { resolve = done; }))
    .mockResolvedValueOnce({ ...settings, project_id: "two", title: "New project" });
  vi.spyOn(api, "getProjectMembers").mockResolvedValue(access);
  const view = render(<ProjectSettingsView />);
  projectId = "two"; view.rerender(<ProjectSettingsView />);
  await screen.findByDisplayValue("New project");
  await act(async () => resolve(settings));
  expect(screen.queryByDisplayValue("Original title")).not.toBeInTheDocument();
});
