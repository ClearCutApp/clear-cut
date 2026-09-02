import type { ReactElement } from "react";

import type { TrackerItem, TrackerState } from "../../api/client";
import { StateBadge } from "../atoms/StateBadge";

export interface TrackerRowProps {
  item: TrackerItem;
  onStateChange: (itemId: string, state: TrackerState) => void;
  onDraftEmail: (itemId: string) => void;
  onNotify: (itemId: string) => void;
  pending?: boolean;
}

const TRACKER_STATES: TrackerState[] = ["BLOCKED", "IN_PROGRESS", "CLEARED"];

/** `value`, or `placeholder` when the server sent an empty string -- the
 * seeded continuity item carries `contact`, `litigation_posture` and `note`
 * all as `""`, never `null` (CHECKPOINTS.md CP-054), and a bare empty
 * string next to its label reads as a dangling colon. */
function orPlaceholder(value: string, placeholder: string): string {
  return value.length > 0 ? value : placeholder;
}

/**
 * One tracker item, with the mutation callbacks `TrackerDashboard` (the
 * container) implements. Presentational: it renders `item` and invokes
 * `onStateChange` / `onDraftEmail` / `onNotify`, but never calls
 * `patchTrackerState` or `postTrackerAction` itself. Only the two actions
 * the server implements get a button -- `generate_document` and
 * `stakeholder_link` 500 (routes.py `_build_action`).
 *
 * `pending` (Don Norman: visibility of system status) is set by the
 * container while a mutation for this item is in flight, and disables the
 * select and both buttons so a second click cannot race the first.
 */
export function TrackerRow({
  item,
  onStateChange,
  onDraftEmail,
  onNotify,
  pending = false,
}: TrackerRowProps): ReactElement {
  const selectId = `tracker-state-${item.item_id}`;
  return (
    <div className="tracker-row" data-testid="tracker-row">
      <div className="tracker-row__top">
        <StateBadge state={item.state} />
        <span className="tracker-row__contact">
          Contact: {orPlaceholder(item.contact, "no contact on file")}
        </span>
        <span className="tracker-row__document">
          Required document: {item.required_document}
        </span>
      </div>

      <dl className="tracker-row__meta">
        <div className="tracker-row__field">
          <dt>Litigation posture</dt>
          <dd>
            {orPlaceholder(
              item.litigation_posture,
              "no litigation history on file",
            )}
          </dd>
        </div>
        <div className="tracker-row__field">
          <dt>Note</dt>
          <dd>{orPlaceholder(item.note, "no notes")}</dd>
        </div>
      </dl>

      <div className="tracker-row__controls">
        <label htmlFor={selectId}>State</label>
        <select
          id={selectId}
          value={item.state}
          disabled={pending}
          onChange={(event) =>
            onStateChange(item.item_id, event.target.value as TrackerState)
          }
        >
          {TRACKER_STATES.map((state) => (
            <option key={state} value={state}>
              {state}
            </option>
          ))}
        </select>

        <button
          type="button"
          className="button button--secondary"
          disabled={pending}
          onClick={() => onDraftEmail(item.item_id)}
        >
          Draft email
        </button>
        <button
          type="button"
          className="button button--secondary"
          disabled={pending}
          onClick={() => onNotify(item.item_id)}
        >
          Notify
        </button>
      </div>

      {item.draft_email !== null && (
        <p className="draft-email" data-testid="draft-email-text">
          {item.draft_email}
        </p>
      )}
    </div>
  );
}
