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

  it("offers a language control and honest workspace context", () => {
    renderTopBar();
    expect(screen.getByRole("button", { name: "English / Español" })).toBeInTheDocument();
    expect(screen.getByText("Production workspace")).toBeInTheDocument();
    expect(screen.queryByText(/this API does not have/)).toBeNull();
  });
});
