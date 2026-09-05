import { useMemo, useState, type ReactElement } from "react";
import { Link } from "react-router";

import { EmptyState } from "../components/atoms/EmptyState";
import { ErrorNotice } from "../components/atoms/ErrorNotice";
import { TrackerFilters } from "../features/tracker/TrackerFilters";
import { applyFilter, groupByState, searchItems, trackerStats, type TrackerFilterValue } from "../features/tracker/model";
import { TrackerStats } from "../features/tracker/TrackerStats";
import { TrackerTable } from "../features/tracker/TrackerTable";
import { useProject } from "../state/ProjectContext";

/**
 * The project's tracker: loading while the mount GET is out, the server's
 * own sentence when it fails, a worded empty state with the way out when
 * no analysis ever ran, and otherwise the stats, filters and the table
 * grouped by state. Filter and search state live here because they narrow
 * what the table renders, not what the data layer holds.
 */
export function OverviewView(): ReactElement {
  const { projectId, tracker, trackerError, selectedItemId, selectItem } = useProject();
  const [filter, setFilter] = useState<TrackerFilterValue>("ALL");
  const [search, setSearch] = useState("");
  const analyzePath = `/projects/${encodeURIComponent(projectId)}/analyze`;

  const groups = useMemo(() => {
    if (tracker === null) {
      return [];
    }
    return groupByState(searchItems(applyFilter(tracker, filter), search));
  }, [tracker, filter, search]);

  return (
    <section className="tracker">
      <h2>Overview</h2>
      <ErrorNotice message={trackerError} />
      {tracker === null && trackerError === null && (
        <p>Loading the tracker for this project.</p>
      )}
      {tracker !== null && tracker.length === 0 && (
        <EmptyState title="No analysis has run yet for this project.">
          <Link to={analyzePath}>Run analysis</Link>
        </EmptyState>
      )}
      {tracker !== null && tracker.length > 0 && (
        <>
          <TrackerStats stats={trackerStats(tracker)} />
          <TrackerFilters
            filter={filter}
            onFilterChange={setFilter}
            search={search}
            onSearchChange={setSearch}
            stats={trackerStats(tracker)}
          />
          <TrackerTable groups={groups} selectedItemId={selectedItemId} onSelect={selectItem} />
        </>
      )}
    </section>
  );
}
