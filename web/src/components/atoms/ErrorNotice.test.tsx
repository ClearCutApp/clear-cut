import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorNotice } from "./ErrorNotice";

describe("ErrorNotice", () => {
  it("announces the message as an alert", () => {
    render(<ErrorNotice message="gcs_uri is required" />);

    expect(screen.getByRole("alert")).toHaveTextContent("gcs_uri is required");
  });

  it("renders nothing without a message", () => {
    const { container } = render(<ErrorNotice message={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing for an empty message", () => {
    const { container } = render(<ErrorNotice message="" />);

    expect(container).toBeEmptyDOMElement();
  });
});
