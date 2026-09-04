import type { ReactElement } from "react";

import { useProject } from "../../state/ProjectContext";

const TITLE_ID = "item-panel-title";

/**
 * The container for the selected item's detail panel. This minimal host
 * renders the selected id and a way to close it; the panel with finding
 * and tracker facts, state changes and actions replaces it.
 */
export function ItemDetailPanelHost(): ReactElement | null {
  const { selectedItemId, selectItem } = useProject();
  if (selectedItemId === null) {
    return null;
  }
  return (
    <aside className="item-panel" role="dialog" aria-labelledby={TITLE_ID}>
      <h2 id={TITLE_ID}>{selectedItemId}</h2>
      <button
        type="button"
        className="button button--secondary"
        onClick={() => selectItem(null)}
      >
        Close
      </button>
    </aside>
  );
}
