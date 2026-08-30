import type { ReactElement } from "react";

/**
 * Application shell. The three surfaces (ScriptView, TrackerDashboard,
 * ProjectQA) land here in phase 4, once the backend routes exist
 * (SDD Section 4.2, ADR 0009). This checkpoint only scaffolds the toolchain
 * and the typed API client, so the shell renders a placeholder.
 */
export function App(): ReactElement {
  return <p>ClearCut</p>;
}
