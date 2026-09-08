import type { AnalysisJob, AnalysisState } from "../../api/client";

/**
 * The polling policy for a queued analysis. Queueing answers 202 with a
 * job, so the browser -- not the server -- decides how often to ask and
 * when to give up. That is a rule with edges (how long is too long, what a
 * failed job says, what an empty error message means), so it lives here as
 * plain functions a test can drive, not inside an effect.
 */

/** The wait before the first re-read. Document AI needs minutes on a
 * feature, but a delta run over a few changed scenes can finish in one. */
export const FIRST_DELAY_MS = 1_000;

/** The ceiling the backoff climbs to. Past this an extra wait buys nothing
 * but a staler answer on screen. */
export const MAX_DELAY_MS = 8_000;

/** How long the browser keeps asking. A run whose instance was reclaimed
 * is reported as FAILED by the read that finds it stale, so this bound
 * exists for a lost connection, not for a stalled job. */
export const TIMEOUT_MS = 15 * 60 * 1_000;

const TERMINAL_STATES: readonly AnalysisState[] = ["SUCCEEDED", "FAILED", "CANCELLED"];

const UNATTRIBUTED_FAILURE =
  "The analysis failed and the server gave no reason.";

export const TIMED_OUT_MESSAGE =
  "The analysis is still running. It keeps running on the server; reload this project to pick it up.";

export function isTerminal(state: AnalysisState): boolean {
  return TERMINAL_STATES.includes(state);
}

/** Doubles from `FIRST_DELAY_MS` and stops at `MAX_DELAY_MS`. `attempt` is
 * how many reads have already been answered, so the first wait is index 0. */
export function delayFor(attempt: number): number {
  const doubled = FIRST_DELAY_MS * 2 ** Math.max(attempt, 0);
  return Math.min(doubled, MAX_DELAY_MS);
}

export type PollStep =
  | { kind: "wait"; delayMs: number }
  | { kind: "ready"; scriptId: string }
  | { kind: "failed"; message: string }
  | { kind: "timedOut"; message: string };

/**
 * What to do with the job just read. `elapsedMs` is measured from the 202,
 * and is only consulted for a job still running: a job that reached a
 * terminal state on the very read that crossed the bound is an answer, not
 * a timeout.
 */
export function nextStep(
  job: AnalysisJob,
  attempt: number,
  elapsedMs: number,
): PollStep {
  if (job.state === "SUCCEEDED") {
    return { kind: "ready", scriptId: job.script_id };
  }
  if (job.state === "CANCELLED") return { kind: "failed", message: "The analysis was cancelled." };
  if (job.state === "FAILED") {
    return {
      kind: "failed",
      message: job.error.length > 0 ? job.error : UNATTRIBUTED_FAILURE,
    };
  }
  if (elapsedMs >= TIMEOUT_MS) {
    return { kind: "timedOut", message: TIMED_OUT_MESSAGE };
  }
  return { kind: "wait", delayMs: delayFor(attempt) };
}

export type SettledStep = Exclude<PollStep, { kind: "wait" }>;

export interface PollDependencies {
  /** Re-reads the job. A rejection propagates: the caller folds it into an
   * outcome, because a failed read is not evidence about the analysis. */
  readJob: () => Promise<AnalysisJob>;
  wait: (ms: number) => Promise<void>;
  /** Milliseconds since some fixed origin; only differences are used. */
  now: () => number;
}

/**
 * Reads the job until it settles, sleeping the policy's delay between
 * reads. Takes its clock and its sleep as arguments so a test drives it
 * without fake timers, and so the retry policy stays one testable place.
 */
export async function pollUntilSettled(
  queued: AnalysisJob,
  dependencies: PollDependencies,
): Promise<SettledStep> {
  const startedAt = dependencies.now();
  let job = queued;
  for (let attempt = 0; ; attempt += 1) {
    const step = nextStep(job, attempt, dependencies.now() - startedAt);
    if (step.kind !== "wait") {
      return step;
    }
    await dependencies.wait(step.delayMs);
    job = await dependencies.readJob();
  }
}
