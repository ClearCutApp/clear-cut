import type { ReactElement } from "react";

import { FilterPill } from "../../components/atoms/FilterPill";
import type { TrackerFilterValue, TrackerStatsSummary } from "./model";

export interface TrackerFiltersProps {
  filter: TrackerFilterValue;
  onFilterChange: (filter: TrackerFilterValue) => void;
  search: string;
  onSearchChange: (search: string) => void;
  stats: TrackerStatsSummary;
}

interface PillSpec {
  value: TrackerFilterValue;
  label: string;
  count: number;
}

function pillsFor(stats: TrackerStatsSummary): PillSpec[] {
  return [
    { value: "ALL", label: "All", count: stats.total },
    { value: "BLOCKED", label: "Blocked", count: stats.blocked },
    { value: "IN_PROGRESS", label: "In progress", count: stats.inProgress },
    { value: "CLEARED", label: "Cleared", count: stats.cleared },
    { value: "NEEDS_REVIEW", label: "Needs review", count: stats.needsReview },
  ];
}

/** The five state/review pills plus the free-text search that together
 * narrow the table `TrackerTable` renders below. */
export function TrackerFilters({
  filter,
  onFilterChange,
  search,
  onSearchChange,
  stats,
}: TrackerFiltersProps): ReactElement {
  return (
    <div className="tracker-filters">
      <div className="tracker-filters__pills">
        {pillsFor(stats).map((pill) => (
          <FilterPill
            key={pill.value}
            label={pill.label}
            count={pill.count}
            active={filter === pill.value}
            onClick={() => onFilterChange(pill.value)}
          />
        ))}
      </div>
      <label className="tracker-filters__search" htmlFor="tracker-search">
        Search
        <input
          id="tracker-search"
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
    </div>
  );
}
