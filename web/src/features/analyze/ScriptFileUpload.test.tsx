import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScriptFileUpload, describeSize, rejectionFor } from "./ScriptFileUpload";

function pdf(name: string, size: number, type = "application/pdf"): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("rejectionFor", () => {
  it("accepts a PDF within the limit", () => {
    expect(rejectionFor(pdf("verano.pdf", 1024))).toBeNull();
  });

  it("accepts a PDF the browser gave no type for, on its extension", () => {
    // Some browsers hand over an empty `type` for a file dragged from a
    // network share. The name is the only evidence left, and the server
    // checks the bytes anyway.
    expect(rejectionFor(pdf("verano.PDF", 1024, ""))).toBeNull();
  });

  it("refuses a file that is not a PDF, naming why", () => {
    expect(rejectionFor(pdf("verano.fdx", 1024, "application/xml"))).toContain("Document AI");
  });

  it("refuses a file over 25 MB, naming its size", () => {
    const rejection = rejectionFor(pdf("verano.pdf", 26 * 1024 * 1024));
    expect(rejection).toContain("26.0 MB");
    expect(rejection).toContain("25 MB");
  });

  it("accepts a file at exactly the limit", () => {
    expect(rejectionFor(pdf("verano.pdf", 25 * 1024 * 1024))).toBeNull();
  });
});

describe("describeSize", () => {
  it("reads a small file in KB and a large one in MB", () => {
    expect(describeSize(2048)).toBe("2 KB");
    expect(describeSize(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});

describe("ScriptFileUpload", () => {
  it("hands a valid file up", () => {
    const onChoose = vi.fn();
    render(
      <ScriptFileUpload uploading={false} storedUri={null} error={null} onChoose={onChoose} />,
    );

    const file = pdf("verano.pdf", 1024);
    fireEvent.change(screen.getByLabelText("Screenplay PDF"), { target: { files: [file] } });

    expect(onChoose).toHaveBeenCalledWith(file);
  });

  it("refuses a bad file locally and never spends the upload", () => {
    const onChoose = vi.fn();
    render(
      <ScriptFileUpload uploading={false} storedUri={null} error={null} onChoose={onChoose} />,
    );

    fireEvent.change(screen.getByLabelText("Screenplay PDF"), {
      target: { files: [pdf("verano.fdx", 1024, "application/xml")] },
    });

    expect(onChoose).not.toHaveBeenCalled();
    expect(screen.getByText(/Document AI/)).toBeInTheDocument();
  });

  it("shows the stored uri once an upload lands", () => {
    render(
      <ScriptFileUpload
        uploading={false}
        storedUri="gs://clearcut-scripts/prj-4f2a/verano.pdf"
        error={null}
        onChoose={vi.fn()}
      />,
    );

    expect(screen.getByText("gs://clearcut-scripts/prj-4f2a/verano.pdf")).toBeInTheDocument();
  });

  it("disables the picker while an upload is in flight", () => {
    render(
      <ScriptFileUpload uploading storedUri={null} error={null} onChoose={vi.fn()} />,
    );

    expect(screen.getByLabelText("Screenplay PDF")).toBeDisabled();
    expect(screen.getByText("Storing the screenplay…")).toBeInTheDocument();
  });

  it("shows the server's refusal", () => {
    render(
      <ScriptFileUpload
        uploading={false}
        storedUri={null}
        error="the file is over 25 MiB"
        onChoose={vi.fn()}
      />,
    );

    expect(screen.getByText("the file is over 25 MiB")).toBeInTheDocument();
  });
});
