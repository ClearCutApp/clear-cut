import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { expect, it } from "vitest";
import { emptyScreenplay, ScreenplayAttributes } from "./schema";

it("assigns fresh IDs when pasted blocks duplicate scene and block IDs", () => {
  const initial = emptyScreenplay();
  const editor = new Editor({ extensions: [StarterKit, ScreenplayAttributes], content: initial });
  const original = editor.getJSON().content[0]!;
  editor.commands.insertContentAt(editor.state.doc.content.size, original);
  const paragraphs = editor.getJSON().content.filter(node => node.type === "paragraph");
  expect(new Set(paragraphs.map(node => node.attrs?.blockId)).size).toBe(paragraphs.length);
  const headings = paragraphs.filter(node => node.attrs?.kind === "scene-heading");
  expect(new Set(headings.map(node => node.attrs?.sceneId)).size).toBe(headings.length);
  expect(paragraphs[0]?.attrs?.blockId).toBe(initial.content[0]?.attrs.blockId);
  editor.destroy();
});
