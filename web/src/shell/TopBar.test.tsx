import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TopBar } from "./TopBar";

function renderTopBar(drawerOpen = false, onToggleDrawer = vi.fn()) {
  render(
    <TopBar drawerOpen={drawerOpen} onToggleDrawer={onToggleDrawer} drawerId="drawer" />,
  );
  return onToggleDrawer;
}

describe("TopBar", () => {
  it("carries the brand and a menu button wired to the drawer", () => {
    const onToggleDrawer = renderTopBar();

    const menu = screen.getByRole("button", { name: "Menu" });
    expect(screen.getByText("ClearCut")).toBeInTheDocument();
    expect(menu).toHaveAttribute("aria-controls", "drawer");
    expect(menu).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(menu);
    expect(onToggleDrawer).toHaveBeenCalledTimes(1);
  });

  it("reports the drawer as expanded when it is open", () => {
    renderTopBar(true);

    expect(screen.getByRole("button", { name: "Menu" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("draws the design's three global affordances", () => {
    renderTopBar();

    expect(screen.getByText("Search ClearCut & the web")).toBeInTheDocument();
    expect(screen.getByText("Notifications").closest("li")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByText("Account")).toBeInTheDocument();
  });

  it("offers no search box, no count and no identity, and says why", () => {
    renderTopBar();

    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByText(/this API does not have/)).toBeInTheDocument();
  });
});
