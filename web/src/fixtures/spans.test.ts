import { describe, expect, it } from "vitest";

import { SCRIPT_FIXTURE } from "./index";
import { SPANNED_SCRIPT_FIXTURE } from "./spans";

/**
 * The offsets are hand-written, so they need a guard that they still land
 * on the phrase the finding names. This is the one place a search over the
 * scene text is right: it is checking a fixture against the capture, not
 * positioning a highlight.
 */
describe("the spanned script fixture", () => {
  it("puts every span exactly on its finding's raw text", () => {
    for (const scene of SPANNED_SCRIPT_FIXTURE.scenes) {
      for (const span of scene.spans) {
        const finding = SPANNED_SCRIPT_FIXTURE.findings.find(
          (candidate) => candidate.finding_id === span.finding_id,
        );

        expect([...scene.text].slice(span.start, span.end).join("")).toBe(finding?.raw_text);
      }
    }
  });

  it("leaves the continuity finding unspanned, because its text is a paraphrase", () => {
    const spanned = SPANNED_SCRIPT_FIXTURE.scenes.flatMap((scene) =>
      scene.spans.map((span) => span.finding_id),
    );

    expect(spanned).toEqual(["EVT-001", "EVT-002"]);
    expect(SPANNED_SCRIPT_FIXTURE.findings.map((finding) => finding.finding_id)).toContain(
      "EVT-003",
    );
  });

  it("changes nothing but the spans", () => {
    expect(SPANNED_SCRIPT_FIXTURE.findings).toEqual(SCRIPT_FIXTURE.findings);
    expect(SPANNED_SCRIPT_FIXTURE.scenes.map((scene) => scene.text)).toEqual(
      SCRIPT_FIXTURE.scenes.map((scene) => scene.text),
    );
  });
});
