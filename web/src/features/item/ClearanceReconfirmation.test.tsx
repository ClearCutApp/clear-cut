import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../../api/client";
import { TRACKER_FIXTURE } from "../../fixtures";
import { ClearanceReconfirmation } from "./ClearanceReconfirmation";

afterEach(() => vi.restoreAllMocks());

it("requires explicit acknowledgement and sends the displayed version and revision", async () => {
  const item = { ...TRACKER_FIXTURE[0], version: 4, needs_review: true };
  const save = vi.spyOn(api, "reconfirmClearance").mockResolvedValue({ ...item, version: 5, needs_review: false });
  const onSaved = vi.fn();
  render(<StrictMode><ClearanceReconfirmation item={item} revisionId="revision-2" onSaved={onSaved} /></StrictMode>);
  expect(screen.getByRole("button", { name: "Confirm clearance" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm clearance" }));
  await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
  expect(save).toHaveBeenCalledWith(item.project_id, item.item_id, 4, "revision-2");
});

it("keeps a failed confirmation visible without pretending the item cleared", async () => {
  const save = vi.spyOn(api, "reconfirmClearance").mockRejectedValue(new api.ApiError(409, "changed"));
  const onSaved = vi.fn();
  render(<ClearanceReconfirmation item={TRACKER_FIXTURE[0]} revisionId="revision-2" onSaved={onSaved} />);
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm clearance" }));
  await screen.findByRole("alert");
  expect(save).toHaveBeenCalledOnce();
  expect(onSaved).not.toHaveBeenCalled();
});
