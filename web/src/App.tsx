import { useEffect, useState, type ReactElement } from "react";

import { fetchHealth, type AnalyzeResponse, type ServerMode } from "./api/client";
import { ModeBanner } from "./components/atoms/ModeBanner";
import { ProjectQA } from "./components/organisms/ProjectQA";
import { ScriptView } from "./components/organisms/ScriptView";
import { TrackerDashboard } from "./components/organisms/TrackerDashboard";

// The seeded demo project (`adapters/demo/scenario.py`, D36/CP-043) --
// plain literals here, never inside a component, so nothing under
// `components/` hardcodes a demo value itself.
const DEMO_PROJECT_ID = "demo-project";
const DEMO_GCS_URI = "gs://clearcut-demo/planted-script-v1.pdf";
const DEMO_JURISDICTION_CODE = "AR";
const DEMO_VERSION = 1;

/**
 * Application shell: holds the `analysis` a successful `postAnalyze` call
 * returned, and a `trackerRefresh` counter bumped on every such success so
 * `TrackerDashboard` re-reads without a page reload.
 */
export function App(): ReactElement {
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [trackerRefresh, setTrackerRefresh] = useState(0);
  const [mode, setMode] = useState<ServerMode | null>(null);

  // Asked once, on mount. The mode cannot change under a running server, and
  // a failed check leaves `mode` null so the banner stays hidden -- claiming
  // real data is planted would be its own kind of lie.
  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((health) => {
        if (!cancelled) {
          setMode(health.mode);
        }
      })
      .catch(() => {
        // Deliberately silent: an unreachable health endpoint is not evidence
        // about the data, so it changes nothing on the page.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleAnalyzed(response: AnalyzeResponse): void {
    setAnalysis(response);
    setTrackerRefresh((count) => count + 1);
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1>ClearCut</h1>
      </header>
      <ModeBanner mode={mode} />
      <ScriptView
        analysis={analysis}
        onAnalyzed={handleAnalyzed}
        projectId={DEMO_PROJECT_ID}
        gcsUri={DEMO_GCS_URI}
        jurisdictionCode={DEMO_JURISDICTION_CODE}
        version={DEMO_VERSION}
      />
      <TrackerDashboard projectId={DEMO_PROJECT_ID} refreshKey={trackerRefresh} />
      <ProjectQA
        projectId={DEMO_PROJECT_ID}
        jurisdictionCode={DEMO_JURISDICTION_CODE}
      />
    </main>
  );
}
