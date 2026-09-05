import type { ReactElement } from "react";

import { jurisdictionName } from "../../theme/jurisdictions";
import type { ProjectFilterValue, ProjectTab } from "./model";

export interface ProjectFiltersProps {
  tabs: ProjectTab[];
  filter: ProjectFilterValue;
  onFilterChange: (filter: ProjectFilterValue) => void;
  search: string;
  onSearchChange: (search: string) => void;
}

function tabLabel(tab: ProjectTab): string {
  return tab.code === null ? "All projects" : jurisdictionName(tab.code);
}

function tabClass(active: boolean): string {
  return active ? "project-tab project-tab--active" : "project-tab";
}

/**
 * The filter row above the project list: one tab per jurisdiction the list
 * contains, with its count, plus the free-text search. A tab names the
 * jurisdiction in words; the code is the value it filters by, not the label
 * a reader has to decode.
 */
export function ProjectFilters({
  tabs,
  filter,
  onFilterChange,
  search,
  onSearchChange,
}: ProjectFiltersProps): ReactElement {
  return (
    <div className="project-filters">
      <div className="project-filters__tabs" role="tablist" aria-label="Filter by jurisdiction">
        {tabs.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            className={tabClass(filter === tab.value)}
            aria-selected={filter === tab.value}
            onClick={() => onFilterChange(tab.value)}
          >
            {tabLabel(tab)}{" "}
            <span className="project-tab__count">{tab.count}</span>
          </button>
        ))}
      </div>
      <label className="project-filters__search" htmlFor="project-search">
        Search
        <input
          id="project-search"
          type="search"
          placeholder="Title or id"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
    </div>
  );
}
