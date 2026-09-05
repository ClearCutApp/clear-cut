import { Bell, Mail } from "lucide-react";
import { useId, useState, type FormEvent, type ReactElement } from "react";

export interface ItemActionsProps {
  pending: boolean;
  onDraftEmail: () => void;
  onNotify: (reason: string) => void;
}

/**
 * The two actions the server implements for a tracker item, and nothing
 * else. Assign, suggest alternatives, request authorization, find rights
 * holder and download have no route behind them and are recorded in the
 * Missing API registry rather than drawn as disabled buttons.
 *
 * Notify is a form rather than a bare button because the contract refuses a
 * notification with no reason (400): "a notification with no reason tells
 * the producer nothing an unsent one would not". The field is required, so
 * the browser stops an empty one before the request is spent.
 *
 * Both controls sit out a pending mutation so a second click cannot race
 * the first.
 */
export function ItemActions({
  pending,
  onDraftEmail,
  onNotify,
}: ItemActionsProps): ReactElement {
  const reasonId = useId();
  const [reason, setReason] = useState("");

  function handleNotify(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onNotify(reason);
    setReason("");
  }

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
      <form className="item-actions__notify" onSubmit={handleNotify}>
        <div className="field">
          <label htmlFor={reasonId}>Reason to notify the producer</label>
          <input
            id={reasonId}
            type="text"
            required
            value={reason}
            disabled={pending}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        <button type="submit" className="button button--secondary" disabled={pending}>
          <Bell aria-hidden="true" size={14} />
          Notify
        </button>
      </form>
    </div>
  );
}
