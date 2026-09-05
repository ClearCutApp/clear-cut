import { Bell, Mail } from "lucide-react";
import type { ReactElement } from "react";

export interface ItemActionsProps {
  pending: boolean;
  onDraftEmail: () => void;
  onNotify: () => void;
}

/**
 * The two actions the server implements for a tracker item, and nothing
 * else: `draft_email` and `notify` are the only values `_build_action`
 * accepts. Assign, suggest alternatives, request authorization, find
 * rights holder and download have no route behind them and are recorded
 * in the Missing API registry rather than drawn as disabled buttons.
 * Both buttons sit out a pending mutation so a second click cannot race
 * the first.
 */
export function ItemActions({
  pending,
  onDraftEmail,
  onNotify,
}: ItemActionsProps): ReactElement {
  return (
    <div className="item-actions">
      <button
        type="button"
        className="button button--secondary"
        disabled={pending}
        onClick={onDraftEmail}
      >
        <Mail aria-hidden="true" size={14} />
        Draft email
      </button>
      <button
        type="button"
        className="button button--secondary"
        disabled={pending}
        onClick={onNotify}
      >
        <Bell aria-hidden="true" size={14} />
        Notify
      </button>
    </div>
  );
}
