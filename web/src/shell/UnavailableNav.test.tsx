import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UnavailableNav } from "./UnavailableNav";

const entries = [
  { label: "Documents", icon: null },
  { label: "Reports", icon: null },
];

describe("UnavailableNav", () => {
  it("draws every entry the design has, and its heading", () => {
    render(<UnavailableNav label="Organization" entries={entries} reason="No resource." />);

    expect(screen.getByText("Organization")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Reports")).toBeInTheDocument();
  });

  it("gives the reason once, in words, next to the entries it explains", () => {
    render(
      <UnavailableNav
        entries={entries}
        reason="Documents and reports have no resource on this API."
      />,
    );

    expect(
      screen.getByText("Documents and reports have no resource on this API."),
    ).toBeInTheDocument();
  });

  it("offers no link and no button, so nothing here can be followed to a 404", () => {
    render(<UnavailableNav entries={entries} reason="No resource." />);

    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Documents")).toHaveAttribute("aria-disabled", "true");
  });

  it("omits the heading when the group has none", () => {
    const { container } = render(
      <UnavailableNav entries={entries} reason="No resource." />,
    );

    expect(container.querySelector(".sidebar__group-label")).toBeNull();
  });
});
