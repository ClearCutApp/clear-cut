import { useId, type ReactElement } from "react";

import { CitationList } from "./FindingFacts";
import { useLocale } from "../../state/LocaleContext";
import type { TrackerItem, TrackerState } from "../../api/client";

export interface TrackerFactsProps {
  item: TrackerItem;
  pending: boolean;
  onStateChange: (state: TrackerState) => void;
}

/** Every transition is legal server-side, so the select offers all three. */
const TRACKER_STATES: readonly TrackerState[] = ["BLOCKED", "IN_PROGRESS", "CLEARED"];

const UPDATED_AT_FORMAT = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

/** `value`, or `placeholder` when the server sent an empty string: the
 * seeded continuity item carries `contact`, `litigation_posture` and `note`
 * as `""`, never `null`, and a bare empty string next to its label reads as
 * a dangling colon. */
function orPlaceholder(value: string, placeholder: string): string {
  return value.length > 0 ? value : placeholder;
}

/** The reader's locale and zone; an unparseable stamp is shown verbatim
 * rather than as "Invalid Date". */
function formatUpdatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : UPDATED_AT_FORMAT.format(date);
}

/**
 * What the tracker knows about the item: its state as a labelled select,
 * the contact, litigation posture and note with worded placeholders, the
 * draft email once one was generated, and the row's version and last
 * update. Presentational: the select reports the chosen state and the
 * container runs the PATCH; the badge in the panel header changes only
 * when the server's row comes back.
 */
export function TrackerFacts({ item, pending, onStateChange }: TrackerFactsProps): ReactElement {
  const { text } = useLocale();
  const titleId = useId();
  const selectId = useId();
  return (
    <section className="item-facts" aria-labelledby={titleId}>
      <h3 id={titleId} className="item-facts__title">
        Tracker
      </h3>
      <div className="field">
        <label htmlFor={selectId}>State</label>
        <select
          id={selectId}
          value={item.state}
          disabled={pending}
          onChange={(event) => onStateChange(event.target.value as TrackerState)}
        >
          {TRACKER_STATES.map((state) => (
            <option key={state} value={state}>
              {state}
            </option>
          ))}
        </select>
      </div>
      <dl className="item-facts__list">
        <div className="item-facts__row">
          <dt>Contact</dt>
          <dd>{orPlaceholder(item.contact, "no contact on file")}</dd>
        </div>
        <div className="item-facts__row">
          <dt>Litigation posture</dt>
          <dd>{orPlaceholder(item.litigation_posture, "no litigation history on file")}</dd>
        </div>
        <div className="item-facts__row">
          <dt>Note</dt>
          <dd>{orPlaceholder(item.note, "no notes")}</dd>
        </div>
      </dl>
      <h3 className="item-facts__title">{text("Rights-holder research", "Investigación del titular de derechos")}</h3>
      <CitationList citations={item.rights_holder_citations ?? []} emptyText={text("No cited rights-holder evidence recorded.", "No hay evidencia citada del titular de derechos.")} />
      {item.draft_email !== null && (
        <>
          <h3 className="item-facts__title">Draft email</h3>
          <pre className="item-facts__draft">{item.draft_email}</pre>
        </>
      )}
      <p className="item-facts__meta">
        Version {item.version}, updated{" "}
        <time dateTime={item.updated_at}>{formatUpdatedAt(item.updated_at)}</time>
      </p>
    </section>
  );
}
