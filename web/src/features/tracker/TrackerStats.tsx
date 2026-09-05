import type { CSSProperties, ReactElement } from "react";

import type { TrackerStatsSummary } from "./model";

export interface TrackerStatsProps {
  stats: TrackerStatsSummary;
}

interface StatSpec {
  label: string;
  value: number;
  detail: string;
  tone: string;
}

function statsFor(stats: TrackerStatsSummary): StatSpec[] {
  return [
    {
      label: "Blocked",
      value: stats.blocked,
      detail: "Waiting on a document",
      tone: "tracker-summary__value--blocked",
    },
    {
      label: "In progress",
      value: stats.inProgress,
      detail: "Someone is on it",
      tone: "tracker-summary__value--in-progress",
    },
    {
      label: "Needs review",
      value: stats.needsReview,
      detail: "Cleared, then the scene changed",
      tone: "tracker-summary__value--needs-review",
    },
  ];
}

/**
 * The headline card: the cleared share as a ring, then the three counts a
 * reader scans next. The ring is a conic gradient driven by
 * `--cleared-percent`, and the same percent is written inside it, so the
 * number is never carried by the sweep alone (.claude/WRITING.md Section 2).
 *
 * The counts come from the whole tracker, so a filter narrowing the table
 * below never moves them.
 */
export function TrackerStats({ stats }: TrackerStatsProps): ReactElement {
  const ring = { "--cleared-percent": stats.clearedPercent } as CSSProperties;
  return (
    <div className="tracker-summary">
      <div className="tracker-summary__cleared">
        <div className="tracker-donut" style={ring}>
          <span className="tracker-donut__inner">{stats.clearedPercent}%</span>
        </div>
        <div className="tracker-summary__stat">
          <p className="tracker-summary__value tracker-summary__value--cleared">Cleared</p>
          <p className="tracker-summary__detail">
            {stats.cleared} of {stats.total} items
          </p>
        </div>
      </div>
      {statsFor(stats).map((stat) => (
        <div className="tracker-summary__stat" key={stat.label}>
          <p className={`tracker-summary__value ${stat.tone}`}>{stat.value}</p>
          <p className="tracker-summary__label">{stat.label}</p>
          <p className="tracker-summary__detail">{stat.detail}</p>
        </div>
      ))}
    </div>
  );
}
