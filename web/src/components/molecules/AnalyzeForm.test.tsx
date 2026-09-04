import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnalyzeForm } from "./AnalyzeForm";

const initialProps = {
  initialProjectId: "demo-project",
  initialGcsUri: "gs://clearcut-demo/planted-script-v1.pdf",
  initialJurisdictionCode: "AR",
  initialVersion: 1,
  submitting: false,
  error: null,
};

describe("AnalyzeForm", () => {
  it("prefills the four demo fields as text inputs, not a file picker", () => {
    render(<AnalyzeForm {...initialProps} onSubmit={vi.fn()} />);

    expect(screen.getByLabelText(/gcs uri/i)).toHaveValue(
      "gs://clearcut-demo/planted-script-v1.pdf",
    );
    expect(screen.getByLabelText(/gcs uri/i)).toHaveAttribute("type", "text");
    expect(screen.getByLabelText(/project/i)).toHaveValue("demo-project");
    expect(screen.getByLabelText(/jurisdiction/i)).toHaveValue("AR");
    expect(screen.getByLabelText(/version/i)).toHaveValue(1);
    expect(screen.queryByRole("button", { name: /choose file/i })).toBeNull();
  });

  it("calls onSubmit with the current field values on submit", () => {
    const onSubmit = vi.fn();
    render(<AnalyzeForm {...initialProps} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      gcs_uri: "gs://clearcut-demo/planted-script-v1.pdf",
      version: 1,
      jurisdiction_code: "AR",
    });
  });

  it("renders the ApiError message when present", () => {
    render(
      <AnalyzeForm
        {...initialProps}
        error="gcs_uri is required"
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("gcs_uri is required")).toBeInTheDocument();
  });
});
