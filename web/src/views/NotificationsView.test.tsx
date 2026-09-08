import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { NotificationsView } from "./NotificationsView";
let projectId = "one";
const selectItem = vi.fn();
vi.mock("../state/ProjectContext", () => ({ useProject: () => ({ projectId, selectItem }) }));
afterEach(() => { vi.restoreAllMocks(); projectId = "one"; selectItem.mockReset(); });
const record: api.ProjectNotification = {
  notification_id: "notice", item_id: "asset", item_version: 2, actor: "producer", reason: "Please review",
  created_at: "2026-09-06T12:00:00Z", read: false, delivery: "in_app_only",
};
it("distinguishes private recording from delivery and only marks read after success", async () => {
  vi.spyOn(api, "getProjectNotifications").mockResolvedValue({ configured: true, notifications: [record], next_cursor: null });
  const read = vi.spyOn(api, "readProjectNotification").mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ read: true });
  render(<NotificationsView />);
  await screen.findByText("Please review");
  expect(screen.getByText(/In this project/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Mark read" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
  await screen.findByText("Read");
  expect(read).toHaveBeenLastCalledWith("one", "notice");
  fireEvent.click(screen.getByRole("button", { name: "Open clearance" }));
  expect(selectItem).toHaveBeenCalledWith("asset");
});
it("ignores a private notification response after project switch", async () => {
  let resolve!: (page: api.NotificationPage) => void;
  vi.spyOn(api, "getProjectNotifications").mockReturnValueOnce(new Promise(done => { resolve = done; }))
    .mockResolvedValueOnce({ configured: true, notifications: [], next_cursor: null });
  const view = render(<NotificationsView />);
  projectId = "two"; view.rerender(<NotificationsView />);
  await screen.findByText("No notifications yet.");
  await act(async () => resolve({ configured: true, notifications: [record], next_cursor: null }));
  await waitFor(() => expect(screen.queryByText("Please review")).not.toBeInTheDocument());
});
