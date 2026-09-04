import type { ReactElement } from "react";

/**
 * Where an analysis is started. The form and the pipeline note arrive with
 * the analyze feature; the heading is what the route answers with today.
 */
export function AnalyzeView(): ReactElement {
  return (
    <section className="analyze">
      <h2>Run analysis</h2>
    </section>
  );
}
