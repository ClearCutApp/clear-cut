import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { NotFoundView } from "./NotFoundView";

describe("NotFoundView", () => {
  it("says the page does not exist and links back to the projects", () => {
    render(
      <MemoryRouter>
        <NotFoundView />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/");
  });
});
