import { useCallback, useMemo, useState, type ReactElement } from "react";
import { Link } from "react-router";

import type { Category } from "../api/client";
import { EmptyState } from "../components/atoms/EmptyState";
import { ErrorNotice } from "../components/atoms/ErrorNotice";
import {
  applyFilter,
  groupByState,
  searchItems,
  trackerStats,
  type TrackerFilterValue,
} from "../features/tracker/model";
import { TrackerFilters } from "../features/tracker/TrackerFilters";
import { TrackerStats } from "../features/tracker/TrackerStats";
import { TrackerTable } from "../features/tracker/TrackerTable";
import { useLocale } from "../state/LocaleContext";
import { useProject } from "../state/ProjectContext";

/**
 * The project's tracker: loading while the mount GET is out, the server's
 * own sentence when it fails, a worded empty state with the way out when
 * no analysis ever ran, and otherwise the cleared ring, the filters and the
 * table grouped by state. Filter and search state live here because they
 * narrow what the table renders, not what the data layer holds.
 *
 * The Type column is joined here rather than in the table, because the join
 * is between two of the data layer's collections and the table should not
 * know there are two.
 */
export function OverviewView(): ReactElement {
  const { text, locale } = useLocale();
  const { projectId, tracker, trackerError, analysisError, selectedItemId, selectItem, findingFor } =
    useProject();
  const [filter, setFilter] = useState<TrackerFilterValue>("ALL");
  const [search, setSearch] = useState("");
  const analyzePath = `/projects/${encodeURIComponent(projectId)}/analyze`;

  const groups = useMemo(() => {
    if (tracker === null) {
      return [];
    }
    return groupByState(searchItems(applyFilter(tracker, filter), search, locale));
  }, [tracker, filter, search, locale]);

  const categoryFor = useCallback(
    (itemId: string): Category | null => findingFor(itemId)?.category ?? null,
    [findingFor],
  );

  return (
    <section className="tracker">
      <h2>{text("Overview", "Resumen")}</h2>
      <ErrorNotice message={trackerError} />
      <ErrorNotice message={analysisError} />
      {tracker === null && trackerError === null && (
        <p role="status">{text("Loading the tracker for this project.", "Cargando las autorizaciones de este proyecto.")}</p>
      )}
      {tracker !== null && tracker.length === 0 && (
        <EmptyState title={text("No analysis has run yet for this project.", "Aún no se ha analizado este proyecto.")}>
          <Link to={analyzePath}>{text("Run analysis", "Analizar guion")}</Link>
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
          <TrackerTable
            groups={groups}
            selectedItemId={selectedItemId}
            onSelect={selectItem}
            categoryFor={categoryFor}
          />
        </>
      )}
    </section>
  );
}
