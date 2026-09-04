import { describe, expect, it } from "vitest";

import { DEMO_PROJECT } from "./demo";

describe("DEMO_PROJECT", () => {
  it("names the planted scenario the mock server serves", () => {
    expect(DEMO_PROJECT.projectId).toBe("demo-project");
    expect(DEMO_PROJECT.gcsUri).toBe("gs://clearcut-demo/planted-script-v1.pdf");
    expect(DEMO_PROJECT.jurisdictionCode).toBe("AR");
    expect(DEMO_PROJECT.version).toBe(1);
  });

  it("points at a bucket object, never a local file", () => {
    expect(DEMO_PROJECT.gcsUri.startsWith("gs://")).toBe(true);
  });
});
