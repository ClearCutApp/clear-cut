import { useCallback, useState, type ReactElement } from "react";

import type { TrackerItem } from "../../api/client";
import { ErrorNotice } from "../../components/atoms/ErrorNotice";
import type { Outcome } from "../../state/outcome";
import { useProject } from "../../state/ProjectContext";
import { jurisdictionName } from "../../theme/jurisdictions";
import { ItemDetailPanel, ItemPanelFrame } from "./ItemDetailPanel";

/** A failed mutation, pinned to the item it was tried on so it never
 * shows under another item's title. */
interface MutationError {
  itemId: string;
  message: string;
}

interface MutationErrorState {
  /** Runs a mutation and keeps its failure message, clearing any older one. */
  record: (itemId: string, mutation: Promise<Outcome<TrackerItem>>) => Promise<boolean>;
  messageFor: (itemId: string) => string | null;
}

function useMutationError(): MutationErrorState {
  const [error, setError] = useState<MutationError | null>(null);
  const record = useCallback(
    async (itemId: string, mutation: Promise<Outcome<TrackerItem>>): Promise<boolean> => {
      setError(null);
      const outcome = await mutation;
      if (!outcome.ok) {
        setError({ itemId, message: outcome.message });
      }
      return outcome.ok;
    },
    [],
  );
  const messageFor = useCallback(
    (itemId: string): string | null => (error?.itemId === itemId ? error.message : null),
    [error],
  );
  return { record, messageFor };
}

/** Why the selected id has no row yet: the GET is still out, it failed
 * (the notice carries the server's sentence), or the tracker answered
 * without it. */
function missingItemSentence(tracker: TrackerItem[] | null, trackerError: string | null): string {
  if (tracker !== null) {
    return "This item is not in the tracker.";
  }
  return trackerError === null
    ? "Loading the tracker for this item."
    : "The tracker could not be loaded for this item.";
}

/**
 * The container for the selected item's detail panel. Reads the selection
 * and the tracker from the data layer, joins the item to its finding when
 * an analysis is in session, and wires the three mutations. A mutation
 * failure is shown inside the panel, next to the control that caused it;
 * the row itself stays as the server last returned it (CP-054).
 */
export function ItemDetailPanelHost(): ReactElement | null {
  const project = useProject();
  const { selectedItemId, tracker, trackerError, selectItem } = project;
  const { record, messageFor } = useMutationError();
  const close = useCallback(() => selectItem(null), [selectItem]);

  if (selectedItemId === null) {
    return null;
  }

  const item = tracker?.find((candidate) => candidate.item_id === selectedItemId) ?? null;
  if (item === null) {
    return (
      <ItemPanelFrame title={selectedItemId} onClose={close}>
        <p className="item-panel__note">{missingItemSentence(tracker, trackerError)}</p>
        <ErrorNotice message={trackerError} />
      </ItemPanelFrame>
    );
  }

  const id = item.item_id;
  return (
    <ItemDetailPanel
      item={item}
      finding={project.findingFor(id)}
      jurisdictionName={jurisdictionName(project.jurisdictionCode)}
      pending={project.pendingItemIds.has(id)}
      error={messageFor(id)}
      onStateChange={(state) => void record(id, project.changeState(id, state))}
      onDraftEmail={() => void record(id, project.draftEmail(id))}
      onNotify={(reason) => record(id, project.notify(id, reason))}
      onClose={close}
      onReload={() => void project.refreshTracker()}
      confirmationRevision={project.analysis?.clearance_bindings?.[id]?.present
        && project.analysis.clearance_bindings[id]?.revision_id === project.analysis.revision_id
        ? project.analysis.revision_id : undefined}
    />
  );
}
