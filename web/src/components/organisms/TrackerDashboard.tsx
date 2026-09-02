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

function withId(ids: Set<string>, itemId: string): Set<string> {
  return new Set(ids).add(itemId);
}

function withoutId(ids: Set<string>, itemId: string): Set<string> {
  const next = new Set(ids);
  next.delete(itemId);
  return next;
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
  const [pendingItemIds, setPendingItemIds] = useState<Set<string>>(
    new Set(),
  );

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

  /**
   * Marks `itemId` pending for the duration of `request` (Don Norman:
   * visibility of system status) so `TrackerRow` can disable its select and
   * both buttons and a second click cannot race the first.
   */
  function runMutation(
    itemId: string,
    request: () => Promise<TrackerItem>,
  ): void {
    setPendingItemIds((current) => withId(current, itemId));
    request()
      .then((updated) =>
        setItems((current) =>
          current === null ? current : replaceItem(current, updated),
        ),
      )
      .catch(handleMutationError)
      .finally(() =>
        setPendingItemIds((current) => withoutId(current, itemId)),
      );
  }

  function handleStateChange(itemId: string, state: TrackerState): void {
    runMutation(itemId, () => patchTrackerState(itemId, state));
  }

  function handleDraftEmail(itemId: string): void {
    runMutation(itemId, () => postTrackerAction(itemId, "draft_email"));
  }

  function handleNotify(itemId: string): void {
    runMutation(itemId, () => postTrackerAction(itemId, "notify"));
  }

  return (
    <section className="tracker-dashboard">
      <h2>Compliance tracker</h2>
      {error !== null && (
        <p className="error-panel" role="alert">
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
            pending={pendingItemIds.has(item.item_id)}
          />
        ))}
    </section>
  );
}
