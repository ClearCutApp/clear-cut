import { useEffect, useState, type ReactElement } from "react";

import {
  ApiError,
  fetchTracker,
  patchTrackerState,
  postTrackerAction,
  type TrackerItem,
  type TrackerState,
} from "../../api/client";
import { TrackerRow } from "../molecules/TrackerRow";

export interface TrackerDashboardProps {
  projectId: string;
  refreshKey: number;
}

const GENERIC_TRACKER_ERROR = "The tracker request failed unexpectedly.";
const EMPTY_STATE_MESSAGE =
  "No analysis has run yet -- the tracker will populate once one completes.";

function replaceItem(items: TrackerItem[], updated: TrackerItem): TrackerItem[] {
  return items.map((item) => (item.item_id === updated.item_id ? updated : item));
}

/**
 * Container for the compliance tracker: fetches on mount and whenever
 * `refreshKey` changes (bumped by `App` after a successful analyze), and
 * owns the mutation callbacks `TrackerRow` calls. Each mutation replaces
 * that row from the response it gets back rather than re-fetching the
 * whole list or mutating local state optimistically.
 */
export function TrackerDashboard({
  projectId,
  refreshKey,
}: TrackerDashboardProps): ReactElement {
  const [items, setItems] = useState<TrackerItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTracker(projectId)
      .then((fetched) => {
        if (!cancelled) {
          setItems(fetched);
          setError(null);
        }
      })
      .catch((thrown: unknown) => {
        if (!cancelled) {
          setError(thrown instanceof ApiError ? thrown.message : GENERIC_TRACKER_ERROR);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, refreshKey]);

  function handleMutationError(thrown: unknown): void {
    setError(thrown instanceof ApiError ? thrown.message : GENERIC_TRACKER_ERROR);
  }

  function handleStateChange(itemId: string, state: TrackerState): void {
    patchTrackerState(itemId, state)
      .then((updated) => setItems((current) => (current === null ? current : replaceItem(current, updated))))
      .catch(handleMutationError);
  }

  function handleDraftEmail(itemId: string): void {
    postTrackerAction(itemId, "draft_email")
      .then((updated) => setItems((current) => (current === null ? current : replaceItem(current, updated))))
      .catch(handleMutationError);
  }

  function handleNotify(itemId: string): void {
    postTrackerAction(itemId, "notify")
      .then((updated) => setItems((current) => (current === null ? current : replaceItem(current, updated))))
      .catch(handleMutationError);
  }

  return (
    <section className="tracker-dashboard">
      <h2>Compliance tracker</h2>
      {error !== null && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {items !== null && items.length === 0 && (
        <p className="empty-state">{EMPTY_STATE_MESSAGE}</p>
      )}
      {items !== null &&
        items.map((item) => (
          <TrackerRow
            key={item.item_id}
            item={item}
            onStateChange={handleStateChange}
            onDraftEmail={handleDraftEmail}
            onNotify={handleNotify}
          />
        ))}
    </section>
  );
}
