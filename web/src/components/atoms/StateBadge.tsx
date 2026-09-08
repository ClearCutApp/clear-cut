import { useLocale } from "../../state/LocaleContext";
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

/** `BLOCKED` -> `blocked`, `IN_PROGRESS` -> `in-progress`: the CSS modifier
 * suffix for `state-badge--<state>`. */
function modifier(state: TrackerState): string {
  return state.toLowerCase().replace(/_/g, "-");
}

/**
 * Renders the tracker state as its word, never a colored circle
 * (.claude/WRITING.md Section 2). Presentational only: no data fetching,
 * no import from `src/api/`. `state-badge--<state>` carries the color;
 * `index.css` owns it, never a `[data-testid]` selector (D61).
 */
export function StateBadge({ state }: StateBadgeProps): ReactElement {
  const { text } = useLocale();
  return (
    <span
      className={`state-badge state-badge--${modifier(state)}`}
      data-testid="state-badge"
    >
      {text(state, { BLOCKED: "BLOQUEADO", IN_PROGRESS: "EN CURSO", CLEARED: "AUTORIZADO" }[state])}
    </span>
  );
}
