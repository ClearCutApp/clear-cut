import { useLocale } from "../../state/LocaleContext";
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

function statsFor(stats: TrackerStatsSummary, text: (en: string, es: string) => string): StatSpec[] {
  return [
    {
      label: text("Blocked", "Bloqueados"),
      value: stats.blocked,
      detail: text("Waiting on a document", "Esperando documentación"),
      tone: "tracker-summary__value--blocked",
    },
    {
      label: text("In progress", "En curso"),
      value: stats.inProgress,
      detail: text("Someone is on it", "Trabajo en curso"),
      tone: "tracker-summary__value--in-progress",
    },
    {
      label: text("Needs review", "Requieren revisión"),
      value: stats.needsReview,
      detail: text("Cleared, then the scene changed", "La escena cambió tras la autorización"),
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
  const { text } = useLocale();
  const ring = { "--cleared-percent": stats.clearedPercent } as CSSProperties;
  return (
    <div className="tracker-summary">
      <div className="tracker-summary__cleared">
        <div className="tracker-donut" style={ring}>
          <span className="tracker-donut__inner">{stats.clearedPercent}%</span>
        </div>
        <div className="tracker-summary__stat">
          <p className="tracker-summary__value tracker-summary__value--cleared">{text("Cleared", "Autorizados")}</p>
          <p className="tracker-summary__detail">
            {text(`${stats.cleared} of ${stats.total} items`, `${stats.cleared} de ${stats.total} elementos`)}
          </p>
        </div>
      </div>
      {statsFor(stats, text).map((stat) => (
        <div className="tracker-summary__stat" key={stat.label}>
          <p className={`tracker-summary__value ${stat.tone}`}>{stat.value}</p>
          <p className="tracker-summary__label">{stat.label}</p>
          <p className="tracker-summary__detail">{stat.detail}</p>
        </div>
      ))}
    </div>
  );
}
