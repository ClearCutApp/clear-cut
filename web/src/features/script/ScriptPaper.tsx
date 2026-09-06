import type { CSSProperties, ReactElement } from "react";

import type { ScriptLine, ScriptRun } from "./model";

export interface ScriptPaperProps {
  lines: ScriptLine[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
  /** The zoom percentage from the toolbar; 100 is the printed size. */
  zoom: number;
}

interface MarkProps {
  run: ScriptRun;
  selected: boolean;
  onSelect: () => void;
}

/**
 * One finding's highlight. It is a button because clicking it selects the
 * finding, and a reader who cannot use a mouse must be able to reach it
 * from the keyboard like any other control.
 */
function Mark({ run, selected, onSelect }: MarkProps): ReactElement {
  const tone = (run.risk ?? "low").toLowerCase();
  const classes = ["script-mark", `script-mark--${tone}`];
  if (selected) {
    classes.push("script-mark--selected");
  }
  return (
    <button
      type="button"
      className={classes.join(" ")}
      aria-pressed={selected}
      onClick={onSelect}
    >
      {run.text}
    </button>
  );
}

/**
 * The risk dot beside a line number. It carries its level as words for a
 * screen reader, because a colour alone says nothing (.claude/WRITING.md
 * Section 2).
 */
function GutterDot({ line }: { line: ScriptLine }): ReactElement | null {
  if (line.risk === null) {
    return null;
  }
  return (
    <span
      className={`script-paper__dot script-paper__dot--${line.risk.toLowerCase()}`}
      role="img"
      aria-label={`${line.risk} risk on line ${line.number}`}
    />
  );
}

/**
 * The script as printed paper: white, monospace, every line numbered, with
 * the analysis's findings highlighted where its offsets put them. Nothing
 * here searches the text -- the runs arrive already cut (`model.ts`), so a
 * phrase flagged three times is marked three times and a finding with no
 * offsets is marked nowhere at all rather than guessed at.
 *
 * The paper is not editable. The API serves a script version to read and
 * has no endpoint that writes one back, so the text is selectable and
 * nothing more.
 */
export function ScriptPaper({
  lines,
  selectedFindingId,
  onSelectFinding,
  zoom,
}: ScriptPaperProps): ReactElement {
  const scale = { "--script-zoom": `${zoom}%` } as CSSProperties;
  return (
    <div className="script-paper" style={scale}>
      {lines.map((line) => (
        <div className="script-paper__row" key={line.number}>
          <span className="script-paper__gutter">
            <GutterDot line={line} />
          </span>
          <span className="script-paper__number" aria-hidden="true">
            {line.number}
          </span>
          <p className={`script-paper__line script-paper__line--${line.kind}`}>
            {line.runs.map((run, index) => {
              const { findingId } = run;
              if (findingId === null) {
                return <span key={index}>{run.text}</span>;
              }
              return (
                <Mark
                  key={index}
                  run={run}
                  selected={findingId === selectedFindingId}
                  onSelect={() => onSelectFinding(findingId)}
                />
              );
            })}
          </p>
        </div>
      ))}
    </div>
  );
}
