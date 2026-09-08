import { useLocale } from "../../state/LocaleContext";
import { Bell, Mail } from "lucide-react";
import { useId, useState, type FormEvent, type ReactElement } from "react";

export interface ItemActionsProps {
  pending: boolean;
  onDraftEmail: () => void;
  onNotify: (reason: string) => void | Promise<boolean | void>;
}

export function ItemActions({
  pending,
  onDraftEmail,
  onNotify,
}: ItemActionsProps): ReactElement {
  const { text } = useLocale();
  const [recorded, setRecorded] = useState(false);
  const reasonId = useId();
  const [reason, setReason] = useState("");

  async function handleNotify(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setRecorded(false);
    try {
      const accepted = await onNotify(reason);
      if (accepted !== false) { setReason(""); setRecorded(true); }
    } catch { /* The container shows the request failure; preserve the draft. */ }
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
        {text("Draft email", "Preparar borrador")}
      </button>
      <form className="item-actions__notify" onSubmit={handleNotify}>
        <div className="field">
          <label htmlFor={reasonId}>{text("Reason to notify the producer", "Motivo para notificar al productor")}</label>
          <input
            id={reasonId}
            type="text"
            required
            maxLength={2000}
            value={reason}
            disabled={pending}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        <button type="submit" className="button button--secondary" disabled={pending}>
          <Bell aria-hidden="true" size={14} />
          {text("Notify", "Notificar")}
        </button>
      </form>
      {recorded && <p role="status">{text("Notification recorded.", "Notificación registrada.")}</p>}
    </div>
  );
}
