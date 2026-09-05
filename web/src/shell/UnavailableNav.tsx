import type { ReactElement, ReactNode } from "react";

export interface UnavailableEntry {
  label: string;
  icon: ReactNode;
}

export interface UnavailableNavProps {
  /** The group heading, when the design gives the entries one. */
  label?: string;
  entries: UnavailableEntry[];
  /** Why none of them opens, in one sentence a producer can act on. */
  reason: string;
}

/**
 * Navigation the design draws that this API cannot serve: the entries are
 * shown, greyed and unclickable, above one sentence saying why.
 *
 * Drawing them is the point. Silently dropping them would let a reader
 * assume the feature is elsewhere; drawing them as working links would send
 * them to a 404. One shared reason per group, rather than one per entry,
 * because the entries in a group are missing for the same reason and
 * repeating it four times reads as noise instead of as an admission.
 *
 * They are plain spans, never disabled buttons: a disabled button says "not
 * now", and these are not coming back until the resource exists.
 */
export function UnavailableNav({
  label,
  entries,
  reason,
}: UnavailableNavProps): ReactElement {
  return (
    <div className="sidebar__group">
      {label !== undefined && <p className="sidebar__group-label">{label}</p>}
      <ul className="sidebar__unavailable-list">
        {entries.map((entry) => (
          <li key={entry.label} className="sidebar__unavailable" aria-disabled="true">
            {entry.icon}
            {entry.label}
          </li>
        ))}
      </ul>
      <p className="sidebar__note">{reason}</p>
    </div>
  );
}
