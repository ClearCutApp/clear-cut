import type { TrackerItem, TrackerState } from "../../api/client";

export interface TrackerStatsSummary {
  total: number;
  cleared: number;
  clearedPercent: number;
  inProgress: number;
  blocked: number;
  needsReview: number;
}

export interface TrackerGroup {
  state: TrackerState;
  items: TrackerItem[];
}

export type TrackerFilterValue = "ALL" | TrackerState | "NEEDS_REVIEW";

const STATE_ORDER: TrackerState[] = ["BLOCKED", "IN_PROGRESS", "CLEARED"];

/** "Scene 1" for one scene, "Scenes 1, 3" for several -- the searchable
 * label a row shows next to its finding and document. */
export function sceneLabel(sceneNumbers: number[], locale: "en" | "es" = "en"): string {
  const noun = locale === "es"
    ? (sceneNumbers.length === 1 ? "Escena" : "Escenas")
    : (sceneNumbers.length === 1 ? "Scene" : "Scenes");
  return `${noun} ${sceneNumbers.join(", ")}`;
}

function countByState(items: TrackerItem[], state: TrackerState): number {
  return items.filter((item) => item.state === state && !item.needs_review).length;
}

/** The five headline numbers `TrackerStats` renders, computed from the
 * full tracker so a filter narrowing the table below never moves them. */
export function trackerStats(items: TrackerItem[]): TrackerStatsSummary {
  const total = items.length;
  const cleared = countByState(items, "CLEARED");
  const clearedPercent = total === 0 ? 0 : Math.round((cleared / total) * 100);
  return {
    total,
    cleared,
    clearedPercent,
    inProgress: countByState(items, "IN_PROGRESS"),
    blocked: countByState(items, "BLOCKED"),
    needsReview: items.filter((item) => item.needs_review).length,
  };
}

/** Groups `items` by state in BLOCKED, IN_PROGRESS, CLEARED order, omitting
 * a state with no rows rather than emitting an empty section. */
export function groupByState(items: TrackerItem[]): TrackerGroup[] {
  return STATE_ORDER.map((state) => ({
    state,
    items: items.filter((item) => item.state === state),
  })).filter((group) => group.items.length > 0);
}

/** Narrows `items` to one state, to items flagged `needs_review`, or passes
 * every item through for `ALL`. */
export function applyFilter(items: TrackerItem[], filter: TrackerFilterValue): TrackerItem[] {
  if (filter === "ALL") {
    return items;
  }
  if (filter === "NEEDS_REVIEW") {
    return items.filter((item) => item.needs_review);
  }
  return items.filter((item) => item.state === filter && !item.needs_review);
}

/** Case-insensitive substring search over the fields a reader would
 * recognise a row by: the required document, the contact, the finding id,
 * and the scene label. A blank query returns every item unchanged. */
export function searchItems(items: TrackerItem[], query: string, locale: "en" | "es" = "en"): TrackerItem[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) {
    return items;
  }
  return items.filter((item) =>
    [item.required_document, item.contact, item.finding_id, sceneLabel(item.scene_numbers, locale)].some(
      (field) => field.toLowerCase().includes(needle),
    ),
  );
}
