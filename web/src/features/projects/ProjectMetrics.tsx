import type { ReactElement } from "react";

import { useLocale } from "../../state/LocaleContext";
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

function metricsFor(metrics: Metrics, text: (en: string, es: string) => string): MetricSpec[] {
  return [
    {
      label: text("Projects", "Proyectos"),
      value: String(metrics.total),
      detail: text("Assigned to you", "Asignados a ti"),
      tone: "stat-card--green",
    },
    {
      label: text("Jurisdictions", "Jurisdicciones"),
      value: String(metrics.jurisdictions),
      detail: text("Across your projects", "En tus proyectos"),
      tone: "stat-card--blue",
    },
    {
      label: text("Added this week", "Añadidos esta semana"),
      value: String(metrics.addedThisWeek),
      detail: text("Created in the last seven days", "Creados en los últimos siete días"),
      tone: "stat-card--amber",
    },
  ];
}

/** Counts derived from the authorized project list. */
export function ProjectMetrics({ metrics }: ProjectMetricsProps): ReactElement {
  const { text } = useLocale();
  return (
    <div className="project-metrics">
      {metricsFor(metrics, text).map((metric) => (
        <div className={`stat-card ${metric.tone}`} key={metric.label}>
          <p className="stat-card__value">{metric.value}</p>
          <p className="stat-card__label">{metric.label}</p>
          <p className="stat-card__detail">{metric.detail}</p>
        </div>
      ))}

    </div>
  );
}
