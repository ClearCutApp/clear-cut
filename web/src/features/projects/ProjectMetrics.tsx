import type { ReactElement } from "react";

import type { ProjectMetrics as Metrics } from "./model";

export interface ProjectMetricsProps {
  metrics: Metrics;
}

interface MetricSpec {
  label: string;
  value: string;
  detail: string;
  tone: string;
}

function metricsFor(metrics: Metrics): MetricSpec[] {
  return [
    {
      label: "Projects",
      value: String(metrics.total),
      detail: "On this server",
      tone: "stat-card--green",
    },
    {
      label: "Jurisdictions",
      value: String(metrics.jurisdictions),
      detail: "Across the projects above",
      tone: "stat-card--blue",
    },
    {
      label: "Added this week",
      value: String(metrics.addedThisWeek),
      detail: "Created in the last seven days",
      tone: "stat-card--amber",
    },
  ];
}

/**
 * The design's four metric cards, filled with the three numbers a project
 * list carries and one card that says why the fourth is missing.
 *
 * The design's Pending clearances, Risks and Items cleared are all tracker
 * totals, and the tracker is read per project: there is no endpoint that
 * sums them across projects, and summing them in the browser would mean one
 * request per row on the landing screen. The card says that instead of
 * showing a number nobody computed.
 */
export function ProjectMetrics({ metrics }: ProjectMetricsProps): ReactElement {
  return (
    <div className="project-metrics">
      {metricsFor(metrics).map((metric) => (
        <div className={`stat-card ${metric.tone}`} key={metric.label}>
          <p className="stat-card__value">{metric.value}</p>
          <p className="stat-card__label">{metric.label}</p>
          <p className="stat-card__detail">{metric.detail}</p>
        </div>
      ))}
      <div className="stat-card stat-card--unavailable">
        <p className="stat-card__label">Clearance totals</p>
        <p className="stat-card__detail">
          Cleared, pending and flagged counts are read per project. No endpoint
          sums them across projects, so none is shown here.
        </p>
      </div>
    </div>
  );
}
