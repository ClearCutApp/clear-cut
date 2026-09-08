import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api/client";
import { emptyScreenplay } from "../features/editor/schema";
import { EditorView } from "./EditorView";

let projectId = "one";
vi.mock("../state/ProjectContext", () => ({ useProject: () => ({ projectId }) }));
vi.mock("@tiptap/react", () => ({ useEditor: () => null, EditorContent: () => null }));
afterEach(() => { vi.restoreAllMocks(); projectId = "one"; });
const draft: api.ScreenplayDraft = { project_id: "one", version: 3, document: emptyScreenplay(), updated_at: "2026-09-06", updated_by: "writer" };
const document: api.ScreenplayDocument = { type: "doc", content: [{ type: "paragraph", attrs: { blockId: "block", sceneId: "stable", kind: "scene-heading" }, content: [{ type: "text", text: "CITED IMMUTABLE SCENE" }] }] };
const revision: api.ScreenplayRevision = { revision_id: "saved", project_id: "one", draft_version: 1, sha256: "hash", created_at: "2026-09-06", created_by: "writer", document };

it("opens a cited immutable revision and stable scene without changing the draft", async () => {
  vi.spyOn(api, "getDraft").mockResolvedValue(draft);
  vi.spyOn(api, "listRevisions").mockResolvedValue({ revisions: [], next_before_version: null });
  const load = vi.spyOn(api, "getRevision").mockResolvedValue(revision);
  const save = vi.spyOn(api, "saveDraft");
  render(<MemoryRouter initialEntries={["/projects/one/editor?revision=saved&scene=stable"]}><EditorView /></MemoryRouter>);
  expect(await screen.findByText("CITED IMMUTABLE SCENE")).toHaveAttribute("id", "revision-scene-stable");
  expect(load).toHaveBeenCalledWith("one", "saved");
  expect(save).not.toHaveBeenCalled();
});

it("removes the old editor immediately and ignores its late cited revision after project switch", async () => {
  vi.spyOn(api, "getDraft").mockResolvedValueOnce(draft).mockReturnValueOnce(new Promise(() => {}));
  vi.spyOn(api, "listRevisions").mockResolvedValue({ revisions: [], next_before_version: null });
  let resolve!: (value: api.ScreenplayRevision) => void;
  vi.spyOn(api, "getRevision").mockReturnValue(new Promise(done => { resolve = done; }));
  const view = render(<MemoryRouter initialEntries={["/projects/one/editor?revision=saved"]}><EditorView /></MemoryRouter>);
  await screen.findByRole("button", { name: "Save revision" });
  projectId = "two";
  view.rerender(<MemoryRouter><EditorView /></MemoryRouter>);
  await act(async () => resolve(revision));
  expect(screen.queryByRole("button", { name: "Save revision" })).not.toBeInTheDocument();
  expect(screen.queryByText("CITED IMMUTABLE SCENE")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Loading screenplay");
});
