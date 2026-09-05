import type { Scene, Script, TrackerItem } from "../api/client";
import analyzeData from "./analyze.json";
import trackerData from "./tracker.json";

/**
 * The two captured bodies (D60), typed as the frozen contract types them.
 *
 * `analyze.json` was captured in-process from `create_app()` before
 * `docs/api/openapi.yaml` froze, so it records a wire the contract has
 * since moved on from in exactly two ways, both named here rather than
 * left for a reader to trip over:
 *
 * - It nests `tracker_items` inside the analysis. `GET .../scripts/{id}`
 *   returns a `Script`, which has no such field; tracker rows are read from
 *   the project's own tracker collection, and `tracker.json` is that read.
 * - Its scenes predate `spans`. An empty `spans` array is the contract's
 *   own word for "no highlight offsets", so that is what the capture
 *   becomes here -- never an invented offset.
 *
 * Adapting at this seam keeps the captured files byte-for-byte what the
 * server sent, and keeps every test reading one typed shape.
 */
type CapturedScene = Omit<Scene, "spans">;

export interface CapturedAnalysis extends Omit<Script, "scenes"> {
  scenes: CapturedScene[];
  tracker_items: TrackerItem[];
}

/** The capture as it stands on disk, for the tests that pin its keys. */
export const CAPTURED_ANALYSIS = analyzeData as CapturedAnalysis;

export const SCRIPT_FIXTURE: Script = {
  script_id: CAPTURED_ANALYSIS.script_id,
  project_id: CAPTURED_ANALYSIS.project_id,
  version: CAPTURED_ANALYSIS.version,
  gcs_uri: CAPTURED_ANALYSIS.gcs_uri,
  jurisdiction_code: CAPTURED_ANALYSIS.jurisdiction_code,
  scenes: CAPTURED_ANALYSIS.scenes.map((scene) => ({ ...scene, spans: [] })),
  findings: CAPTURED_ANALYSIS.findings,
};

export const TRACKER_FIXTURE = trackerData as TrackerItem[];
