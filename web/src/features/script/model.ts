import type { Finding, RiskLevel, Scene, Span, TrackerItem, TrackerState } from "../../api/client";

/** One stretch of a line: plain prose when `findingId` is null, and one
 * finding's highlight when it is not. */
export interface ScriptRun {
  text: string;
  findingId: string | null;
  risk: RiskLevel | null;
}

/**
 * How a line reads on the page. `slugline` is a scene heading, `transition`
 * a CUT TO: and its kin, `blank` an empty line the script kept, and
 * `action` everything else. The paper styles each; nothing here decides a
 * colour.
 */
export type ScriptLineKind = "slugline" | "transition" | "blank" | "action";

export interface ScriptLine {
  /** One-based and continuous across the whole script, the way a reader
   * counts down a printed page rather than restarting per scene. */
  number: number;
  sceneNumber: number;
  kind: ScriptLineKind;
  runs: ScriptRun[];
  /** The highest risk of any span touching this line, for the gutter dot.
   * Null when the line carries no highlight at all. */
  risk: RiskLevel | null;
}

/** Ascending severity. A comparison reads an index, so a new level added to
 * the contract fails this file's build rather than sorting as unknown. */
const RISK_ORDER: Record<RiskLevel, number> = {
  LOW: 0,
  MEDIUM: 1,
  HIGH: 2,
  CRITICAL: 3,
};

const SLUGLINE = /^(?:INT\.?\/EXT|I\/E|INT|EXT|EST)[.\s]/i;

/**
 * Spans, sorted and made renderable. The server resolves overlaps before
 * it sends them -- where two findings claim the same characters the
 * higher-risk one wins the range and the other arrives with no span at all
 * (`Span` in docs/api/openapi.yaml) -- so this only sorts, drops offsets
 * that fall outside the text, and skips anything still overlapping. HTML
 * cannot nest one mark inside another, and a silently truncated highlight
 * would be a lie about where the finding is.
 */
function placeableSpans(spans: Span[], length: number): Span[] {
  const ordered = [...spans]
    .filter((span) => span.start >= 0 && span.end > span.start && span.end <= length)
    .sort((left, right) => left.start - right.start);
  const placed: Span[] = [];
  let reached = 0;
  for (const span of ordered) {
    if (span.start >= reached) {
      placed.push(span);
      reached = span.end;
    }
  }
  return placed;
}

/**
 * The scene's text as runs, cut at every span boundary. Offsets are
 * counted in Unicode code points (ADR 0015), so the text is walked as an
 * array of code points rather than sliced as a UTF-16 string: an emoji
 * earlier in the scene must not shift a later highlight by one.
 */
function sceneRuns(scene: Scene): ScriptRun[] {
  const characters = [...scene.text];
  const runs: ScriptRun[] = [];
  let cursor = 0;
  for (const span of placeableSpans(scene.spans, characters.length)) {
    if (span.start > cursor) {
      runs.push(plainRun(characters.slice(cursor, span.start).join("")));
    }
    runs.push({
      text: characters.slice(span.start, span.end).join(""),
      findingId: span.finding_id,
      risk: span.risk,
    });
    cursor = span.end;
  }
  if (cursor < characters.length) {
    runs.push(plainRun(characters.slice(cursor).join("")));
  }
  return runs;
}

function plainRun(text: string): ScriptRun {
  return { text, findingId: null, risk: null };
}

/** A transition is an all-caps line that hands off to the next scene. The
 * common ones end in " TO:"; the two that do not are named outright rather
 * than guessed at by a looser pattern. */
function isTransition(line: string): boolean {
  const trimmed = line.trim();
  if (trimmed.length === 0 || trimmed !== trimmed.toUpperCase()) {
    return false;
  }
  return trimmed.endsWith(" TO:") || trimmed === "FADE IN:" || trimmed === "FADE OUT.";
}

function lineKind(text: string): ScriptLineKind {
  if (text.trim().length === 0) {
    return "blank";
  }
  if (SLUGLINE.test(text.trim())) {
    return "slugline";
  }
  return isTransition(text) ? "transition" : "action";
}

function highestRisk(runs: ScriptRun[]): RiskLevel | null {
  return runs.reduce<RiskLevel | null>((highest, run) => {
    if (run.risk === null) {
      return highest;
    }
    return highest === null || RISK_ORDER[run.risk] > RISK_ORDER[highest] ? run.risk : highest;
  }, null);
}

/** Cuts `runs` at every newline, so a span crossing a line break becomes
 * one highlighted run on each of the lines it covers. */
function runsToLines(runs: ScriptRun[]): ScriptRun[][] {
  const lines: ScriptRun[][] = [[]];
  for (const run of runs) {
    const pieces = run.text.split("\n");
    pieces.forEach((piece, index) => {
      if (index > 0) {
        lines.push([]);
      }
      if (piece.length > 0) {
        lines[lines.length - 1].push({ ...run, text: piece });
      }
    });
  }
  return lines;
}

/**
 * Every scene's text as numbered lines the paper renders directly: the
 * runs to draw, what kind of line it is, and the gutter dot's risk. The
 * highlights come from the server's offsets and nothing here ever searches
 * the text for a phrase (ADR 0015).
 */
export function scriptLines(scenes: Scene[]): ScriptLine[] {
  const lines: ScriptLine[] = [];
  for (const scene of scenes) {
    for (const runs of runsToLines(sceneRuns(scene))) {
      lines.push({
        number: lines.length + 1,
        sceneNumber: scene.number,
        kind: lineKind(runs.map((run) => run.text).join("")),
        runs,
        risk: highestRisk(runs),
      });
    }
  }
  return lines;
}

/** Words across every scene, counted the way a word processor counts them:
 * whitespace-separated runs of characters, sluglines and transitions
 * included, because they are on the page too. */
export function wordCount(scenes: Scene[]): number {
  return scenes.reduce(
    (total, scene) => total + scene.text.split(/\s+/).filter((word) => word.length > 0).length,
    0,
  );
}

/** A finding as the rail lists it: the analysis's own facts, the tracker's
 * verdict on it, and whether the paper marks it anywhere. */
export interface Suggestion {
  finding: Finding;
  /** The tracker row's state, or null when the tracker holds no row for
   * this finding -- which is also what an unloaded tracker looks like. */
  state: TrackerState | null;
  needsReview: boolean;
  /**
   * False when the analysis returned no offsets for this finding. That is
   * ordinary: the model may report a paraphrase of the line rather than a
   * substring of it, and offsets are computed by matching, never guessed.
   * Such a finding is listed here with its scene and page and marked
   * nowhere on the paper.
   */
  hasSpan: boolean;
}

/**
 * The chips over the rail. Two independent cuts through the same list:
 * `HIGH_RISK` and `CONSIDERATIONS` split it by the risk the analysis
 * assigned, `TO_REVIEW` and `CLEARED` by what the tracker says was done
 * about it. Nothing here invents a third axis.
 */
export type SuggestionFilter = "ALL" | "HIGH_RISK" | "TO_REVIEW" | "CONSIDERATIONS" | "CLEARED";

export const SUGGESTION_FILTERS: SuggestionFilter[] = [
  "ALL",
  "HIGH_RISK",
  "TO_REVIEW",
  "CONSIDERATIONS",
  "CLEARED",
];

function isHighRisk(suggestion: Suggestion): boolean {
  return suggestion.finding.risk_level === "HIGH" || suggestion.finding.risk_level === "CRITICAL";
}

/** Document order: the scene first, then the page within it, then the id
 * so two findings on one page never swap places between renders. */
function readingOrder(left: Finding, right: Finding): number {
  return (
    left.scene_number - right.scene_number ||
    left.page - right.page ||
    left.finding_id.localeCompare(right.finding_id)
  );
}

/** Joins each finding to the spans that mark it and to its tracker row,
 * in the order the script reads. */
export function buildSuggestions(
  findings: Finding[],
  scenes: Scene[],
  items: TrackerItem[],
): Suggestion[] {
  const spanned = new Set(scenes.flatMap((scene) => scene.spans).map((span) => span.finding_id));
  return [...findings].sort(readingOrder).map((finding) => {
    const item = items.find((candidate) => candidate.finding_id === finding.finding_id) ?? null;
    return {
      finding,
      state: item?.state ?? null,
      needsReview: item?.needs_review ?? false,
      hasSpan: spanned.has(finding.finding_id),
    };
  });
}

/** Narrows the rail to one chip. A finding the tracker has no row for
 * counts as still to review: nothing has recorded a decision on it. */
export function applySuggestionFilter(
  suggestions: Suggestion[],
  filter: SuggestionFilter,
): Suggestion[] {
  switch (filter) {
    case "ALL":
      return suggestions;
    case "HIGH_RISK":
      return suggestions.filter(isHighRisk);
    case "CONSIDERATIONS":
      return suggestions.filter((suggestion) => !isHighRisk(suggestion));
    case "CLEARED":
      return suggestions.filter((suggestion) => suggestion.state === "CLEARED");
    case "TO_REVIEW":
      return suggestions.filter((suggestion) => suggestion.state !== "CLEARED");
  }
}

/** Each chip's count, taken from the whole list, so narrowing the rail
 * never moves the numbers above it. */
export function suggestionCounts(
  suggestions: Suggestion[],
): Record<SuggestionFilter, number> {
  return {
    ALL: suggestions.length,
    HIGH_RISK: applySuggestionFilter(suggestions, "HIGH_RISK").length,
    TO_REVIEW: applySuggestionFilter(suggestions, "TO_REVIEW").length,
    CONSIDERATIONS: applySuggestionFilter(suggestions, "CONSIDERATIONS").length,
    CLEARED: applySuggestionFilter(suggestions, "CLEARED").length,
  };
}

export interface StepperPosition {
  /** One-based place of the selection in the list, or 0 when the selection
   * is absent or is not in the list the stepper is walking. */
  index: number;
  total: number;
}

export function stepperPosition(
  suggestions: Suggestion[],
  selectedFindingId: string | null,
): StepperPosition {
  const found = suggestions.findIndex(
    (suggestion) => suggestion.finding.finding_id === selectedFindingId,
  );
  return { index: found === -1 ? 0 : found + 1, total: suggestions.length };
}

/**
 * The finding one step away, or null when there is none: the stepper stops
 * at both ends rather than wrapping, so a reader can tell the last issue
 * from the first. With nothing selected yet, either direction opens the
 * first issue, which is where a reader who presses either button wants to
 * begin.
 */
export function neighbourFindingId(
  suggestions: Suggestion[],
  selectedFindingId: string | null,
  direction: 1 | -1,
): string | null {
  if (suggestions.length === 0) {
    return null;
  }
  const current = suggestions.findIndex(
    (suggestion) => suggestion.finding.finding_id === selectedFindingId,
  );
  if (current === -1) {
    return suggestions[0].finding.finding_id;
  }
  const next = current + direction;
  return next < 0 || next >= suggestions.length ? null : suggestions[next].finding.finding_id;
}

/** The zoom steps the paper offers. A ladder rather than free arithmetic,
 * so every stop is a percentage a reader recognises. */
const ZOOM_LADDER = [75, 90, 100, 125, 150, 175, 200];

export const DEFAULT_ZOOM = 100;

function stepZoom(current: number, direction: 1 | -1): number {
  const index = ZOOM_LADDER.indexOf(current);
  if (index === -1) {
    return DEFAULT_ZOOM;
  }
  const next = index + direction;
  return next < 0 || next >= ZOOM_LADDER.length ? current : ZOOM_LADDER[next];
}

export function zoomIn(current: number): number {
  return stepZoom(current, 1);
}

export function zoomOut(current: number): number {
  return stepZoom(current, -1);
}

/** The numbers the pills and the footer carry. `unmarked` is the count of
 * findings the paper highlights nowhere, said out loud rather than left as
 * a discrepancy between the rail and the page. */
export interface ScriptStats {
  scenes: number;
  findings: number;
  highRisk: number;
  unmarked: number;
  words: number;
}

export function scriptStats(scenes: Scene[], suggestions: Suggestion[]): ScriptStats {
  return {
    scenes: scenes.length,
    findings: suggestions.length,
    highRisk: suggestions.filter(isHighRisk).length,
    unmarked: suggestions.filter((suggestion) => !suggestion.hasSpan).length,
    words: wordCount(scenes),
  };
}
