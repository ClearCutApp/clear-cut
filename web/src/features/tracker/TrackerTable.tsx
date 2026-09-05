import type { ReactElement } from "react";

import { EmptyState } from "../../components/atoms/EmptyState";
import type { TrackerGroup } from "./model";
import { TrackerRow } from "./TrackerRow";

export interface TrackerTableProps {
  groups: TrackerGroup[];
  selectedItemId: string | null;
  onSelect: (itemId: string) => void;
}

/**
 * The tracker rows, sectioned by state. `groups` already carries the
 * filter and search narrowing (`OverviewView` computes it); this component
 * only lays the result out, so "no items match" is a fact about the whole
 * table rather than one this component decides on its own.
 */
export function TrackerTable({ groups, selectedItemId, onSelect }: TrackerTableProps): ReactElement {
  if (groups.length === 0) {
    return <EmptyState title="No items match the current filter." />;
  }
  return (
    <div className="tracker-table">
      {groups.map((group) => (
        <section className="tracker-table__group" key={group.state}>
          <h3 className="tracker-table__heading">{group.state}</h3>
          {group.items.map((item) => (
            <TrackerRow
              key={item.item_id}
              item={item}
              selected={item.item_id === selectedItemId}
              onSelect={onSelect}
            />
          ))}
        </section>
      ))}
    </div>
  );
}
