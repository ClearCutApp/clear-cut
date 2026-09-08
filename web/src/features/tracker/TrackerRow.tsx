import type { ReactElement } from "react";

import type { Category, TrackerItem } from "../../api/client";
import { NeedsReviewBadge } from "../../components/atoms/NeedsReviewBadge";
import { StateBadge } from "../../components/atoms/StateBadge";
import { useLocale } from "../../state/LocaleContext";
import { CATEGORY_LABELS, CATEGORY_LABELS_ES } from "../../theme/labels";
import { sceneLabel } from "./model";

export interface TrackerRowProps {
  item: TrackerItem;
  /** The category of the finding this item came from, or null when no
   * script is loaded to join it to. */
  category: Category | null;
  selected: boolean;
  onSelect: (itemId: string) => void;
}

/** `value`, or `placeholder` when the server sent an empty string -- the
 * seeded continuity item carries `contact` as `""`, never `null`
 * (CHECKPOINTS.md CP-054), and a bare empty string next to its label reads
 * as a dangling colon. */
function orPlaceholder(value: string, placeholder: string): string {
  return value.length > 0 ? value : placeholder;
}

/**
 * One tracker item, grouped under its state by `TrackerTable`. The whole
 * row opens the item's detail panel through a single button -- no state
 * select and no action buttons live here (D-plan Section 4: those moved to
 * `ItemDetailPanel`, and the row itself never calls a mutation).
 *
 * The Type column is the finding's category in words. A tracker item does
 * not carry one: it is joined from the loaded script, and reads "unknown"
 * when there is no script to join to, never a guess from the document name.
 */
export function TrackerRow({
  item,
  category,
  selected,
  onSelect,
}: TrackerRowProps): ReactElement {
  const { text, locale } = useLocale();
  return (
    <div className={selected ? "tracker-row tracker-row--selected" : "tracker-row"}>
      <StateBadge state={item.state} />
      <span className="tracker-row__finding">{item.finding_id}</span>
      <span className="tracker-row__document">{item.required_document}</span>
      <span
        className={
          category === null
            ? "tracker-row__type tracker-row__type--unknown"
            : "tracker-row__type"
        }
      >
        {category === null ? text("unknown", "desconocido") : (locale === "es" ? CATEGORY_LABELS_ES : CATEGORY_LABELS)[category]}
      </span>
      <span className="tracker-row__contact">
        {orPlaceholder(item.contact, text("no contact on file", "sin contacto registrado"))}
      </span>
      <span className="tracker-row__scene">{sceneLabel(item.scene_numbers, locale)}</span>
      <NeedsReviewBadge needsReview={item.needs_review} />
      <button
        type="button"
        className="tracker-row__open"
        data-tracker-item-id={item.finding_id}
        aria-current={selected ? "true" : undefined}
        onClick={() => onSelect(item.item_id)}
      >
        {text("Open", "Abrir")} {item.finding_id}
      </button>
    </div>
  );
}
