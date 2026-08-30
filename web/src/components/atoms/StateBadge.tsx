import type { ReactElement } from "react";

/**
 * Local to this atom on purpose: the tracker-state vocabulary has exactly
 * two consumers today (this file and `api/client.ts`), which is the
 * duplicate-twice case AGENT.md Section 4 asks for rather than a shared
 * module. A third caller earns the extraction.
 */
export type TrackerState = "BLOCKED" | "IN_PROGRESS" | "CLEARED";

export interface StateBadgeProps {
  state: TrackerState;
}

/**
 * Renders the tracker state as its word, never a colored circle
 * (.claude/WRITING.md Section 2). Presentational only: no data fetching,
 * no import from `src/api/`.
 */
export function StateBadge({ state }: StateBadgeProps): ReactElement {
  return <span data-testid="state-badge">{state}</span>;
}
