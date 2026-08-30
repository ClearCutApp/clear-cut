import type { ReactElement } from "react";

/**
 * Local to this atom on purpose: the risk vocabulary has exactly two
 * consumers today (this file and `api/client.ts`), which is the duplicate-
 * twice case AGENT.md Section 4 asks for rather than a shared module. A
 * third caller earns the extraction.
 */
export type Risk = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface RiskBadgeProps {
  risk: Risk;
}

/**
 * Renders the risk level as its word, never a color alone
 * (.claude/WRITING.md Section 2). Presentational only: no data fetching,
 * no import from `src/api/`.
 */
export function RiskBadge({ risk }: RiskBadgeProps): ReactElement {
  return <span data-testid="risk-badge">{risk}</span>;
}
