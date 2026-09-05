import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnalyzeForm } from "./AnalyzeForm";

const initialProps = {
  initialGcsUri: "gs://clearcut-demo/planted-script-v1.pdf",
  initialJurisdictionCode: "AR",
  initialVersion: 2,
  submitting: false,
  error: null,
};

describe("AnalyzeForm", () => {
  it("prefills the three request fields as text inputs, not a file picker", () => {
    render(<AnalyzeForm {...initialProps} onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Script URI")).toHaveValue(
      "gs://clearcut-demo/planted-script-v1.pdf",
    );
    expect(screen.getByLabelText("Script URI")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("Jurisdiction code")).toHaveValue("AR");
    expect(screen.getByLabelText("Version")).toHaveValue(2);
    expect(screen.queryByRole("button", { name: /choose file/i })).toBeNull();
  });

  it("asks for no project id: the route names the project", () => {
    render(<AnalyzeForm {...initialProps} onSubmit={vi.fn()} />);

    expect(screen.queryByLabelText(/project/i)).toBeNull();
  });

  it("calls onSubmit with the current field values on submit", () => {
    const onSubmit = vi.fn();
    render(<AnalyzeForm {...initialProps} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    expect(onSubmit).toHaveBeenCalledWith({
      gcs_uri: "gs://clearcut-demo/planted-script-v1.pdf",
      version: 2,
      jurisdiction_code: "AR",
    });
  });

  it("sits out its own request", () => {
    render(<AnalyzeForm {...initialProps} submitting onSubmit={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();
    expect(screen.getByLabelText("Script URI")).toBeDisabled();
  });

  it("announces the server's own sentence as an alert", () => {
    render(
      <AnalyzeForm {...initialProps} error="gcs_uri is required" onSubmit={vi.fn()} />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("gcs_uri is required");
  });
});
