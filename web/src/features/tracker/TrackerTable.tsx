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

const COLUMNS = ["State", "Finding", "Required document", "Type", "Contact", "Scenes"];

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
  if (groups.length === 0) {
    return <EmptyState title="No items match the current filter." />;
  }
  return (
    <div className="tracker-table">
      <div className="tracker-table__columns" aria-hidden="true">
        {COLUMNS.map((column) => (
          <span key={column}>{column}</span>
        ))}
      </div>
      {groups.map((group) => (
        <section className="tracker-table__group" key={group.state}>
          <h3 className="tracker-table__heading">{group.state}</h3>
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
