import { useMemo, useState, type ReactElement } from "react";
import { Link } from "react-router";

import { EmptyState } from "../components/atoms/EmptyState";
import { ErrorNotice } from "../components/atoms/ErrorNotice";
import { IssueStepper } from "../features/script/IssueStepper";
import {
  buildSuggestions,
  DEFAULT_ZOOM,
  neighbourFindingId,
  scriptLines,
  scriptStats,
  stepperPosition,
  zoomIn,
  zoomOut,
  type SuggestionFilter,
} from "../features/script/model";
import { ScriptPaper } from "../features/script/ScriptPaper";
import { ScriptToolbar } from "../features/script/ScriptToolbar";
import { SuggestionsRail } from "../features/script/SuggestionsRail";
import { useProject } from "../state/ProjectContext";

/**
 * The script as paper, with the analysis's findings marked where its
 * offsets put them and listed in the rail beside it.
 *
 * The script version is read back from the server on mount, so a finding
 * survives a reload; an empty state here means no analysis has ever run
 * for this project, not that one was lost.
 *
 * Selecting a finding is one act with two effects: the rail opens its
 * card, and the paper presses its highlight. The selection is the finding
 * id, because that is what both the spans and the findings carry; the
 * tracker's own row for it belongs to the detail panel, which the tracker
 * opens.
 */
export function ScriptView(): ReactElement {
  const { projectId, analysis, analysisError, tracker } = useProject();
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [filter, setFilter] = useState<SuggestionFilter>("ALL");
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const analyzePath = `/projects/${encodeURIComponent(projectId)}/analyze`;

  const scenes = useMemo(() => analysis?.scenes ?? [], [analysis]);
  const lines = useMemo(() => scriptLines(scenes), [scenes]);
  const suggestions = useMemo(
    () => buildSuggestions(analysis?.findings ?? [], scenes, tracker ?? []),
    [analysis, scenes, tracker],
  );
  const stats = scriptStats(scenes, suggestions);
  const position = stepperPosition(suggestions, selectedFindingId);
  const previousId = neighbourFindingId(suggestions, selectedFindingId, -1);
  const nextId = neighbourFindingId(suggestions, selectedFindingId, 1);

  return (
    <section className="script">
      <h2>Script</h2>
      <ErrorNotice message={analysisError} />
      {analysis === null ? (
        <EmptyState title="No analysis has been run for this project.">
          <Link to={analyzePath}>Run analysis</Link>
        </EmptyState>
      ) : (
        <div className="script__layout">
          <div className="script__page">
            <IssueStepper
              position={position}
              stats={stats}
              onPrevious={() => setSelectedFindingId(previousId)}
              onNext={() => setSelectedFindingId(nextId)}
              hasPrevious={previousId !== null}
              hasNext={nextId !== null}
            />
            <ScriptToolbar
              words={stats.words}
              zoom={zoom}
              onZoomIn={() => setZoom(zoomIn(zoom))}
              onZoomOut={() => setZoom(zoomOut(zoom))}
              canZoomIn={zoomIn(zoom) !== zoom}
              canZoomOut={zoomOut(zoom) !== zoom}
            />
            <ScriptPaper
              lines={lines}
              selectedFindingId={selectedFindingId}
              onSelectFinding={setSelectedFindingId}
              zoom={zoom}
            />
          </div>
          <SuggestionsRail
            suggestions={suggestions}
            filter={filter}
            onFilterChange={setFilter}
            selectedFindingId={selectedFindingId}
            onSelectFinding={setSelectedFindingId}
          />
        </div>
      )}
    </section>
  );
}
