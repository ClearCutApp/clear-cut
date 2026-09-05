import type { ReactElement } from "react";

import type { TrackerStatsSummary } from "./model";

export interface TrackerStatsProps {
  stats: TrackerStatsSummary;
}

interface StatSpec {
  label: string;
  value: string;
}

function statsFor(stats: TrackerStatsSummary): StatSpec[] {
  return [
    { label: "Cleared", value: `${stats.cleared} of ${stats.total} (${stats.clearedPercent}%)` },
    { label: "Blocked", value: String(stats.blocked) },
    { label: "In progress", value: String(stats.inProgress) },
    { label: "Needs review", value: String(stats.needsReview) },
  ];
}

/** The headline numbers above the filters: cleared as a fraction of the
 * total with its percent, then the three counts a reader scans first. */
export function TrackerStats({ stats }: TrackerStatsProps): ReactElement {
  return (
    <div className="tracker-stats">
      {statsFor(stats).map((stat) => (
        <div className="stat-card" key={stat.label}>
          <p className="stat-card__value">{stat.value}</p>
          <p className="stat-card__label">{stat.label}</p>
        </div>
      ))}
    </div>
  );
}
