import { describe, expect, it } from "vitest";

import type { AnalysisJob, AnalysisState } from "../../api/client";
import {
  FIRST_DELAY_MS,
  MAX_DELAY_MS,
  TIMED_OUT_MESSAGE,
  TIMEOUT_MS,
  delayFor,
  isTerminal,
  nextStep,
  pollUntilSettled,
} from "./model";

function job(state: AnalysisState, overrides: Partial<AnalysisJob> = {}): AnalysisJob {
  return {
    analysis_id: "ana_1",
    project_id: "proj_1",
    script_id: "scr_1",
    state,
    created_at: "2026-09-05T12:00:00Z",
    updated_at: "2026-09-05T12:00:00Z",
    error: "",
    version: 1,
    ...overrides,
  };
}

describe("isTerminal", () => {
  it("holds only for the two states a job never moves out of", () => {
    expect(isTerminal("SUCCEEDED")).toBe(true);
    expect(isTerminal("FAILED")).toBe(true);
    expect(isTerminal("QUEUED")).toBe(false);
    expect(isTerminal("RUNNING")).toBe(false);
  });
});

describe("delayFor", () => {
  it("starts at the first delay and doubles", () => {
    expect(delayFor(0)).toBe(FIRST_DELAY_MS);
    expect(delayFor(1)).toBe(FIRST_DELAY_MS * 2);
  });

  it("stops climbing at the ceiling", () => {
    expect(delayFor(20)).toBe(MAX_DELAY_MS);
  });
});

describe("nextStep", () => {
  it("hands back the script id a succeeded job carries", () => {
    expect(nextStep(job("SUCCEEDED", { script_id: "scr_9" }), 0, 0)).toEqual({
      kind: "ready",
      scriptId: "scr_9",
    });
  });

  it("reports the server's own sentence for a failed job", () => {
    expect(nextStep(job("FAILED", { error: "Document AI returned no pages" }), 0, 0)).toEqual({
      kind: "failed",
      message: "Document AI returned no pages",
    });
  });

  it("says so plainly when a failed job carries no reason", () => {
    const step = nextStep(job("FAILED"), 0, 0);

    expect(step.kind).toBe("failed");
    expect(step).not.toMatchObject({ message: "" });
  });

  it("keeps waiting while the job is queued or running", () => {
    expect(nextStep(job("QUEUED"), 0, 0)).toEqual({
      kind: "wait",
      delayMs: FIRST_DELAY_MS,
    });
    expect(nextStep(job("RUNNING"), 1, 0)).toEqual({
      kind: "wait",
      delayMs: FIRST_DELAY_MS * 2,
    });
  });

  it("gives up once the bound is crossed, saying the run continues server-side", () => {
    expect(nextStep(job("RUNNING"), 3, TIMEOUT_MS)).toEqual({
      kind: "timedOut",
      message: TIMED_OUT_MESSAGE,
    });
  });

  it("answers a job that succeeded on the read that crossed the bound", () => {
    expect(nextStep(job("SUCCEEDED"), 3, TIMEOUT_MS + 1)).toMatchObject({
      kind: "ready",
    });
  });
});

describe("pollUntilSettled", () => {
  it("re-reads until the job succeeds and backs off between reads", async () => {
    const answers = [job("RUNNING"), job("RUNNING"), job("SUCCEEDED", { script_id: "scr_7" })];
    const waits: number[] = [];

    const settled = await pollUntilSettled(job("QUEUED"), {
      readJob: () => Promise.resolve(answers.shift() as AnalysisJob),
      wait: (ms) => {
        waits.push(ms);
        return Promise.resolve();
      },
      now: () => 0,
    });

    expect(settled).toEqual({ kind: "ready", scriptId: "scr_7" });
    expect(waits).toEqual([FIRST_DELAY_MS, FIRST_DELAY_MS * 2, FIRST_DELAY_MS * 4]);
  });

  it("returns the failure without re-reading a job that arrived failed", async () => {
    let reads = 0;

    const settled = await pollUntilSettled(job("FAILED", { error: "no pages" }), {
      readJob: () => {
        reads += 1;
        return Promise.resolve(job("FAILED"));
      },
      wait: () => Promise.resolve(),
      now: () => 0,
    });

    expect(settled).toEqual({ kind: "failed", message: "no pages" });
    expect(reads).toBe(0);
  });

  it("stops when the clock passes the bound rather than polling forever", async () => {
    let clock = 0;

    const settled = await pollUntilSettled(job("QUEUED"), {
      readJob: () => Promise.resolve(job("RUNNING")),
      wait: () => {
        clock += TIMEOUT_MS;
        return Promise.resolve();
      },
      now: () => clock,
    });

    expect(settled).toEqual({ kind: "timedOut", message: TIMED_OUT_MESSAGE });
  });

  it("lets a failed read reach the caller instead of retrying blind", async () => {
    const failure = pollUntilSettled(job("QUEUED"), {
      readJob: () => Promise.reject(new Error("network down")),
      wait: () => Promise.resolve(),
      now: () => 0,
    });

    await expect(failure).rejects.toThrow("network down");
  });
});
