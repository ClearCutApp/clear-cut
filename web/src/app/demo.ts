/**
 * The seeded demo project (`adapters/demo/scenario.py`, D36/CP-043): the
 * one module allowed to spell these values outside a test
 * (`architecture.test.ts`, demo literal ownership). Views read them through
 * `DEMO_PROJECT`; nothing under `components/`, `features/` or `state/`
 * hardcodes a demo value itself (CP-054).
 */
export interface DemoProject {
  readonly projectId: string;
  readonly gcsUri: string;
  readonly jurisdictionCode: string;
  readonly version: number;
}

export const DEMO_PROJECT: DemoProject = {
  projectId: "demo-project",
  gcsUri: "gs://clearcut-demo/planted-script-v1.pdf",
  jurisdictionCode: "AR",
  version: 1,
};
