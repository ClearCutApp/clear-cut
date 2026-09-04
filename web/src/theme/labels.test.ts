import { describe, expect, it } from "vitest";

import { CATEGORY_LABELS, FACT_KIND_LABELS, NER_LABELS } from "./labels";

describe("labels", () => {
  it("names all eight categories", () => {
    expect(Object.keys(CATEGORY_LABELS)).toHaveLength(8);
    expect(CATEGORY_LABELS.CONTINUITY).toBe("Continuity");
  });

  it("names all eleven NER labels", () => {
    expect(Object.keys(NER_LABELS)).toHaveLength(11);
    expect(NER_LABELS.MUSIC_EXISTING).toBe("Existing music");
  });

  it("names both bible fact kinds", () => {
    expect(Object.keys(FACT_KIND_LABELS)).toHaveLength(2);
    expect(FACT_KIND_LABELS.LORE).toBe("Bible fact");
    expect(FACT_KIND_LABELS.POLICY).toBe("Policy");
  });

  it("never leaves a raw enum token as its own label", () => {
    const labels = [
      ...Object.values(CATEGORY_LABELS),
      ...Object.values(NER_LABELS),
      ...Object.values(FACT_KIND_LABELS),
    ];

    expect(labels.every((label) => !/^[A-Z_]+$/.test(label))).toBe(true);
  });
});
