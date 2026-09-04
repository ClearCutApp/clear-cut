import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NeedsReviewBadge } from "./NeedsReviewBadge";

describe("NeedsReviewBadge", () => {
  it("renders the word when the item needs review", () => {
    render(<NeedsReviewBadge needsReview />);

    expect(screen.getByText("NEEDS_REVIEW")).toBeInTheDocument();
  });

  it("renders nothing when it does not", () => {
    const { container } = render(<NeedsReviewBadge needsReview={false} />);

    expect(container).toBeEmptyDOMElement();
  });
});
