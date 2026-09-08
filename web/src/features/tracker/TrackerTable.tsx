import { useLocale } from "../../state/LocaleContext";
import type { ReactElement } from "react";

import type { Category } from "../../api/client";
import { EmptyState } from "../../components/atoms/EmptyState";
import type { TrackerGroup } from "./model";
import { TrackerRow } from "./TrackerRow";

export interface TrackerTableProps {
  groups: TrackerGroup[];
  selectedItemId: string | null;
  onSelect: (itemId: string) => void;
  /** The finding category behind one item, or null when no script is
   * loaded. Passed as a lookup rather than folded into the group so the
   * grouping stays a fact about tracker state alone. */
  categoryFor: (itemId: string) => Category | null;
}



/**
 * The tracker rows, sectioned by state. `groups` already carries the
 * filter and search narrowing (`OverviewView` computes it); this component
 * only lays the result out, so "no items match" is a fact about the whole
 * table rather than one this component decides on its own.
 */
export function TrackerTable({
  groups,
  selectedItemId,
  onSelect,
  categoryFor,
}: TrackerTableProps): ReactElement {
  const { text } = useLocale();
  if (groups.length === 0) {
    return <EmptyState title={text("No items match the current filter.", "Ningún elemento coincide con el filtro.")} />;
  }
  return (
    <div className="tracker-table">
      <div className="tracker-table__columns" aria-hidden="true">
        {[text("State", "Estado"), text("Finding", "Hallazgo"), text("Required document", "Documento requerido"), text("Type", "Tipo"), text("Contact", "Contacto"), text("Scenes", "Escenas")].map((column) => (
          <span key={column}>{column}</span>
        ))}
      </div>
      {groups.map((group) => (
        <section className="tracker-table__group" key={group.state}>
          <h3 className="tracker-table__heading">{text(group.state, { BLOCKED: "BLOQUEADOS", IN_PROGRESS: "EN CURSO", CLEARED: "AUTORIZADOS" }[group.state])}</h3>
          {group.items.map((item) => (
            <TrackerRow
              key={item.item_id}
              item={item}
              category={categoryFor(item.item_id)}
              selected={item.item_id === selectedItemId}
              onSelect={onSelect}
            />
          ))}
        </section>
      ))}
    </div>
  );
}
