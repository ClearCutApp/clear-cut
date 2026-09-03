import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModeBanner } from "./ModeBanner";

describe("ModeBanner", () => {
  it("says the data is a fixed sample when the server is in mock mode", () => {
    render(<ModeBanner mode="mock" />);

    const banner = screen.getByTestId("mode-banner");
    expect(banner).toBeInTheDocument();
    expect(banner.textContent?.toLowerCase()).toContain("sample");
  });

  it("renders nothing when the server is live", () => {
    render(<ModeBanner mode="live" />);

    expect(screen.queryByTestId("mode-banner")).not.toBeInTheDocument();
  });

  it("renders nothing before the mode is known", () => {
    // The first paint happens before /api/health answers. Showing the banner
    // then would flash a "this is fake" warning over real data; showing
    // nothing errs the other way for one frame, and the banner appears as
    // soon as the answer lands.
    render(<ModeBanner mode={null} />);

    expect(screen.queryByTestId("mode-banner")).not.toBeInTheDocument();
  });

  it("carries a role that assistive technology announces", () => {
    // The whole purpose is to stop someone trusting planted numbers. A
    // warning only sighted users receive does not do that.
    render(<ModeBanner mode="mock" />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
