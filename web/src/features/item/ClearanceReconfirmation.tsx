import { useEffect, useRef, useState } from "react";
import { reconfirmClearance, type TrackerItem } from "../../api/client";
import { useLocale } from "../../state/LocaleContext";

export function ClearanceReconfirmation({ item, revisionId, onSaved }: {
  item: TrackerItem; revisionId: string; onSaved: () => void;
}) {
  const { text } = useLocale();
  const [acknowledged, setAcknowledged] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const confirm = async () => {
    if (!acknowledged) return;
    setPending(true); setError(null);
    try {
      await reconfirmClearance(item.project_id, item.item_id, item.version, revisionId);
      if (alive.current) onSaved();
    } catch { if (alive.current) setError(text("Could not confirm. Reload the clearance and check the current revision before retrying.", "No se pudo confirmar. Recarga la autorización y revisa la versión actual antes de reintentar.")); }
    finally { if (alive.current) setPending(false); }
  };
  return <section className="item-panel__section">
    <h3>{text("Confirm applicability", "Confirmar aplicabilidad")}</h3>
    <p>{text("Analyzed revision", "Revisión analizada")}: {revisionId}</p>
    <label><input type="checkbox" checked={acknowledged} disabled={pending} onChange={event => setAcknowledged(event.target.checked)} />{text("I reviewed this revision, the evidence and clearance conditions, and confirm the permission applies.", "Revisé esta versión, la evidencia y las condiciones, y confirmo que la autorización es aplicable.")}</label>
    <button className="button" disabled={!acknowledged || pending} onClick={() => void confirm()}>{pending ? text("Confirming…", "Confirmando…") : text("Confirm clearance", "Confirmar autorización")}</button>
    {error && <p role="alert">{error}</p>}
  </section>;
}
