import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { TeamView } from "./TeamView";

vi.mock("../state/ServerModeContext", () => ({ useServerMode: () => "live" }));
afterEach(() => vi.restoreAllMocks());

it("creates a human-shared link and does not invent mailbox delivery or project grants", async () => {
  vi.spyOn(api, "listOrganizations").mockResolvedValue([{ organization_id: "org", name: "Studio", role: "owner" }]);
  vi.spyOn(api, "getWorkspaceMembers").mockResolvedValue({ members: [] });
  vi.spyOn(api, "getWorkspaceInvitations").mockResolvedValue({ invitations: [] });
  const invite = vi.spyOn(api, "inviteWorkspaceMember").mockResolvedValue({
    token: "private-token", invitation: { invitation_id: "id", email: "writer@example.com", role: "writer", state: "pending", version: 1, expires_at: "2026-09-13T12:00:00Z" },
  });
  render(<MemoryRouter><TeamView /></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText("Verified account email"), { target: { value: "writer@example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "Create invitation link" }));
  const link = await screen.findByLabelText("Invitation link");
  expect(link).toHaveValue(window.location.origin + "/join#token=private-token");
  expect(invite).toHaveBeenCalledWith("org", "writer@example.com", "writer");
  expect(screen.getByText(/no message has been sent/)).toBeInTheDocument();
});
