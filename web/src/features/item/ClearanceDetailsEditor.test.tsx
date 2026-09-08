import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/client";
import { TRACKER_FIXTURE } from "../../fixtures";
import { ClearanceDetailsEditor } from "./ClearanceDetailsEditor";

afterEach(() => vi.restoreAllMocks());

describe("clearance evidence editing", () => {
  it("submits the loaded version and selected evidence without a state transition", async () => {
    vi.spyOn(api, "listDocuments").mockResolvedValue({ documents: [{ file_id: "proof", filename: "release.pdf" } as api.ProjectDocument], next_before: null });
    const save = vi.spyOn(api, "updateClearanceDetails").mockResolvedValue({ ...TRACKER_FIXTURE[0], version: 2 });
    const onSaved = vi.fn();
    render(<ClearanceDetailsEditor item={TRACKER_FIXTURE[0]} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit details and evidence" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "release.pdf" }));
    fireEvent.change(screen.getByLabelText("Clearance conditions"), { target: { value: "Argentina, one film" } });
    fireEvent.change(screen.getByLabelText("Due date"), { target: { value: "2026-09-08" } });
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(save).toHaveBeenCalledWith(TRACKER_FIXTURE[0].project_id, TRACKER_FIXTURE[0].item_id, 1, expect.objectContaining({ evidence_file_ids: ["proof"], clearance_conditions: "Argentina, one film", due_date: "2026-09-08" }));
    expect(save.mock.calls[0][3]).not.toHaveProperty("state");
  });

  it("retains local notes and the original expected version after a conflict", async () => {
    vi.spyOn(api, "listDocuments").mockResolvedValue({ documents: [], next_before: null });
    const save = vi.spyOn(api, "updateClearanceDetails").mockRejectedValue(new Error("clearance changed; reload it before trying again"));
    const onSaved = vi.fn();
    const view = render(<ClearanceDetailsEditor item={TRACKER_FIXTURE[0]} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit details and evidence" }));
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "Keep my local permission wording" } });
    view.rerender(<ClearanceDetailsEditor item={{ ...TRACKER_FIXTURE[0], version: 3, note: "Other producer" }} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("clearance changed");
    expect(screen.getByLabelText("Note")).toHaveValue("Keep my local permission wording");
    expect(save.mock.calls[0][2]).toBe(1);
    expect(onSaved).not.toHaveBeenCalled();
  });
});
