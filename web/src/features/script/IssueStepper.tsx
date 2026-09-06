import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactElement } from "react";

import type { ScriptStats, StepperPosition } from "./model";

export interface IssueStepperProps {
  position: StepperPosition;
  stats: ScriptStats;
  onPrevious: () => void;
  onNext: () => void;
  hasPrevious: boolean;
  hasNext: boolean;
}

interface PillSpec {
  label: string;
  value: number;
  tone: string;
}

/**
 * The pills next to the stepper. `Not marked` is the count of findings the
 * paper highlights nowhere: the analysis reported a paraphrase of the line
 * rather than a stretch of it, so there is no position to draw. Saying the
 * number out loud is what keeps the rail and the page honest with each
 * other.
 */
function pillsFor(stats: ScriptStats): PillSpec[] {
  return [
    { label: "Scenes", value: stats.scenes, tone: "script-pill--neutral" },
    { label: "Issues", value: stats.findings, tone: "script-pill--neutral" },
    { label: "High risk", value: stats.highRisk, tone: "script-pill--high" },
    { label: "Not marked", value: stats.unmarked, tone: "script-pill--muted" },
  ];
}

/** Walks the findings in the order the script reads them, and carries the
 * counts a reader scans before deciding where to start. */
export function IssueStepper({
  position,
  stats,
  onPrevious,
  onNext,
  hasPrevious,
  hasNext,
}: IssueStepperProps): ReactElement {
  return (
    <div className="script-stepper">
      <ul className="script-stepper__pills">
        {pillsFor(stats).map((pill) => (
          <li key={pill.label} className={`script-pill ${pill.tone}`}>
            <span className="script-pill__value">{pill.value}</span>
            <span className="script-pill__label">{pill.label}</span>
          </li>
        ))}
      </ul>
      <div className="script-stepper__controls">
        <button
          type="button"
          className="script-stepper__button"
          onClick={onPrevious}
          disabled={!hasPrevious}
        >
          <ChevronLeft size={14} aria-hidden="true" />
          Previous issue
        </button>
        <p className="script-stepper__count">
          {position.index === 0 ? "None selected" : `${position.index} of ${position.total}`}
        </p>
        <button
          type="button"
          className="script-stepper__button"
          onClick={onNext}
          disabled={!hasNext}
        >
          Next issue
          <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
