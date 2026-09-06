import { describe, expect, it } from "vitest";

import { EXAMPLE_QUESTIONS, isAskable } from "./model";

describe("EXAMPLE_QUESTIONS", () => {
  it("offers a legal stem and a blocker word so mock answers are grounded", () => {
    expect(EXAMPLE_QUESTIONS).toEqual([
      "Do we need permission for the trademark?",
      "What is blocked right now?",
    ]);
  });

  it("phrases every example as a non-empty question", () => {
    for (const example of EXAMPLE_QUESTIONS) {
      expect(isAskable(example)).toBe(true);
      expect(example.endsWith("?")).toBe(true);
    }
  });
});

describe("isAskable", () => {
  it("rejects an empty or whitespace-only question", () => {
    expect(isAskable("")).toBe(false);
    expect(isAskable(" \n\t ")).toBe(false);
  });

  it("accepts a question with any visible text", () => {
    expect(isAskable("  Why?  ")).toBe(true);
  });
});
