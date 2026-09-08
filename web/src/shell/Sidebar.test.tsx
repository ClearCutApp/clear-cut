import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "firebase/auth";

import { API_DOCS_PATH, type Organization } from "../api/client";
import { Sidebar } from "./Sidebar";

/** The two boundaries this component has: the identity it reads and the one
 *  request it makes. Both are stubbed, so no test here touches `fetch`. */
const boundary = vi.hoisted(() => ({
  user: null as { uid: string } | null,
  organizations: vi.fn(),
  logOut: vi.fn(),
}));

vi.mock("../api/client", async (original) => ({
  ...(await original<typeof import("../api/client")>()),
  listOrganizations: () => boundary.organizations(),
}));
vi.mock("../state/AuthContext", () => ({
  useAuth: () => ({
    user: boundary.user as User | null,
    ready: true,
    configured: true,
    error: null,
  }),
  logOut: () => boundary.logOut(),
}));

const patagonia: Organization = {
  organization_id: "org-patagonia",
  name: "Patagonia Films",
  role: "owner",
};
const nightEchoes: Organization = {
  organization_id: "org-night-echoes",
  name: "Night Echoes",
  role: "producer",
};

function renderSidebar(projectId: string | null, path = "/", onNavigate = vi.fn()) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar projectId={projectId} onNavigate={onNavigate} />
    </MemoryRouter>,
  );
  return onNavigate;
}

beforeEach(() => {
  boundary.user = { uid: "user" };
  boundary.organizations.mockReset().mockResolvedValue([patagonia]);
  boundary.logOut.mockReset();
});

describe("Sidebar navigation", () => {
  it("gives every entry an icon of its own, so no two destinations look alike", async () => {
    renderSidebar("p", "/projects/p");
    await screen.findByText("Patagonia Films");

    const icons = [...document.querySelectorAll("svg")].map(
      (icon) => icon.getAttribute("class") ?? "",
    );

    expect(icons.length).toBeGreaterThan(0);
    expect(new Set(icons).size).toBe(icons.length);
  });

  it("keeps Projects a real link and the project routes reachable", () => {
    renderSidebar("demo x", "/projects/demo%20x");

    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/projects");
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/projects/demo%20x");
    expect(screen.getByRole("link", { name: "Script" })).toHaveAttribute("href", "/projects/demo%20x/script");
    expect(screen.getByRole("link", { name: "Write" })).toHaveAttribute("href", "/projects/demo%20x/editor");
    expect(screen.getByRole("link", { name: "Notifications" })).toHaveAttribute("href", "/projects/demo%20x/notifications");
    expect(screen.getByRole("link", { name: "Production" })).toHaveAttribute("href", "/projects/demo%20x/settings");
  });

  it("shows no project group outside a project", () => {
    renderSidebar(null);

    expect(screen.queryByRole("link", { name: "Overview" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Ask" })).toBeNull();
  });

  it("marks only the current route's entry as current", () => {
    renderSidebar("p", "/projects/p/script");

    expect(screen.getByRole("link", { name: "Script" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Projects" })).not.toHaveAttribute("aria-current");
  });

  it("reports every navigation so a drawer can close", () => {
    const onNavigate = renderSidebar("p");

    fireEvent.click(screen.getByRole("link", { name: "Ask" }));

    expect(onNavigate).toHaveBeenCalledTimes(1);
  });
});

describe("Sidebar workspace", () => {
  it("names the workspace and the role the API returned, and invents nothing else", async () => {
    renderSidebar(null);

    expect(await screen.findByText("Patagonia Films")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(document.querySelector(".sidebar__workspace-avatar")).toHaveTextContent("PF");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("offers no switcher control, because switching would change nothing", async () => {
    boundary.organizations.mockResolvedValue([patagonia, nightEchoes]);
    renderSidebar(null);

    await screen.findByText("Patagonia Films");
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.getByText(/more than one workspace/)).toBeInTheDocument();
  });

  it("draws no workspace block when the identity belongs to none", async () => {
    boundary.organizations.mockResolvedValue([]);
    renderSidebar(null);

    await waitFor(() => expect(boundary.organizations).toHaveBeenCalled());
    expect(document.querySelector(".sidebar__workspace")).toBeNull();
    expect(screen.getByRole("link", { name: "Projects" })).toBeInTheDocument();
  });

  it("keeps the nav standing when the workspace request fails", async () => {
    boundary.organizations.mockRejectedValue(new Error("unavailable"));
    renderSidebar("p");

    await waitFor(() => expect(boundary.organizations).toHaveBeenCalled());
    expect(document.querySelector(".sidebar__workspace")).toBeNull();
    expect(screen.getByRole("link", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Team & Roles" })).toBeInTheDocument();
  });

  it("asks for nothing while there is no identity", () => {
    boundary.user = null;
    renderSidebar(null);

    expect(boundary.organizations).not.toHaveBeenCalled();
    expect(document.querySelector(".sidebar__workspace")).toBeNull();
  });
});

describe("Sidebar organization group", () => {
  it("routes Team & Roles and draws the rest greyed, with one reason", () => {
    renderSidebar(null);

    expect(screen.getByRole("link", { name: "Team & Roles" })).toHaveAttribute("href", "/team");
    for (const label of ["Company & Profile", "Authorized Users", "Settings"]) {
      expect(screen.getByText(label)).toHaveAttribute("aria-disabled", "true");
      expect(screen.queryByRole("link", { name: label })).toBeNull();
    }
    expect(screen.getByText(/no company profile/)).toBeInTheDocument();
  });

  it("says why a global dashboard, clearances and reports do not open", () => {
    renderSidebar(null);

    expect(screen.getByText("Dashboard")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Clearances")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(/one project at a time/)).toBeInTheDocument();
  });
});

describe("Sidebar footer", () => {
  it("links to the API docs at the client's constant", () => {
    renderSidebar(null);

    expect(screen.getByRole("link", { name: "API docs" })).toHaveAttribute("href", API_DOCS_PATH);
  });

  it("draws Help & Support without a destination it does not have", () => {
    renderSidebar(null);

    expect(screen.getByText("Help & Support")).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("link", { name: "Help & Support" })).toBeNull();
  });

  it("signs out through the identity boundary", () => {
    renderSidebar(null);

    fireEvent.click(screen.getByRole("button", { name: "Log Out" }));

    expect(boundary.logOut).toHaveBeenCalledTimes(1);
  });

  it("offers no sign out to an identity that has none", () => {
    boundary.user = null;
    renderSidebar(null);

    expect(screen.queryByRole("button", { name: "Log Out" })).toBeNull();
  });
});
