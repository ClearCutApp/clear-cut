import { Extension } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import type { ScreenplayDocument } from "../../api/client";

export const blockKinds = ["scene-heading", "action", "character", "dialogue", "parenthetical", "transition"] as const;
export function emptyScreenplay(): ScreenplayDocument {
  return { type: "doc", content: [{ type: "paragraph", attrs: { blockId: crypto.randomUUID(), sceneId: crypto.randomUUID(), kind: "scene-heading" } }] };
}
export const ScreenplayAttributes = Extension.create({
  name: "screenplayAttributes",
  addGlobalAttributes() {
    return [{ types: ["paragraph"], attributes: {
      blockId: { default: null, renderHTML: attrs => ({ "data-block-id": attrs.blockId }) },
      sceneId: { default: null, renderHTML: attrs => ({ "data-scene-id": attrs.sceneId }) },
      kind: { default: "action", renderHTML: attrs => ({ "data-kind": attrs.kind }) },
    } }];
  },
  addProseMirrorPlugins() {
    return [new Plugin({ appendTransaction(transactions, _previous, state) {
      if (!transactions.some(transaction => transaction.docChanged)) return null;
      const tr = state.tr;
      const blocks = new Set<string>();
      const scenes = new Set<string>();
      let activeScene = "";
      state.doc.forEach((node, position, index) => {
        if (node.type.name !== "paragraph") return;
        const attrs = { ...node.attrs };
        if (!attrs.blockId || blocks.has(attrs.blockId)) attrs.blockId = crypto.randomUUID();
        blocks.add(attrs.blockId);
        if (index === 0) attrs.kind = "scene-heading";
        if (attrs.kind === "scene-heading") {
          if (!attrs.sceneId || scenes.has(attrs.sceneId)) attrs.sceneId = crypto.randomUUID();
          activeScene = attrs.sceneId;
          scenes.add(activeScene);
        } else attrs.sceneId = activeScene;
        if (Object.keys(attrs).some(key => attrs[key] !== node.attrs[key])) tr.setNodeMarkup(position, undefined, attrs);
      });
      return tr.docChanged ? tr : null;
    } })];
  },
});
