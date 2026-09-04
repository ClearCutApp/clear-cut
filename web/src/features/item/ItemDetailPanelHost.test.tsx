import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProject } from "../../testing/renderWithProject";
import { ItemDetailPanelHost } from "./ItemDetailPanelHost";

describe("ItemDetailPanelHost", () => {
  it("renders nothing while no item is selected", () => {
    renderWithProject(<ItemDetailPanelHost />);

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("names the selected item and closes on request", async () => {
    renderWithProject(<ItemDetailPanelHost />, { selectedItemId: "EVT-002" });

    expect(await screen.findByRole("dialog", { name: "EVT-002" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
