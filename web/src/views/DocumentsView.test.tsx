import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { DocumentsView } from "./DocumentsView";

let projectId = "one";
vi.mock("../state/ProjectContext", () => ({ useProject: () => ({ projectId }) }));
afterEach(() => { vi.restoreAllMocks(); projectId = "one"; });

it("ignores late documents from the previous project", async () => {
  let resolveFirst!: (page: api.DocumentPage) => void;
  vi.spyOn(api, "listDocuments")
    .mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve; }))
    .mockResolvedValueOnce({ documents: [], next_before: null });
  const view = render(<DocumentsView />);
  projectId = "two";
  view.rerender(<DocumentsView />);
  await screen.findByText("No documents yet. Import a screenplay or upload evidence.");
  await act(async () => resolveFirst({ documents: [{ file_id: "private", filename: "Private screenplay" } as api.ProjectDocument], next_before: null }));
  expect(screen.queryByText("Private screenplay")).not.toBeInTheDocument();
});
