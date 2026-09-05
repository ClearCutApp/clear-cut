import type { ReactElement } from "react";

import type { TrackerItem } from "../../api/client";
import { NeedsReviewBadge } from "../../components/atoms/NeedsReviewBadge";
import { StateBadge } from "../../components/atoms/StateBadge";
import { sceneLabel } from "./model";

export interface TrackerRowProps {
  item: TrackerItem;
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
 */
export function TrackerRow({ item, selected, onSelect }: TrackerRowProps): ReactElement {
  return (
    <div className="tracker-row">
      <StateBadge state={item.state} />
      <span className="tracker-row__finding">{item.finding_id}</span>
      <span className="tracker-row__document">{item.required_document}</span>
      <span className="tracker-row__contact">
        {orPlaceholder(item.contact, "no contact on file")}
      </span>
      <span className="tracker-row__scene">{sceneLabel(item.scene_numbers)}</span>
      <NeedsReviewBadge needsReview={item.needs_review} />
      <button
        type="button"
        className="tracker-row__open"
        aria-current={selected ? "true" : undefined}
        onClick={() => onSelect(item.item_id)}
      >
        Open {item.finding_id}
      </button>
    </div>
  );
}
