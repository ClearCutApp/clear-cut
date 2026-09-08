import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import {
  askProjectQuestion,
  uploadScriptFile,
  createScript,
  createTrackerItemEmailDraft,
  createTrackerItemNotification,
  getAnalysis,
  getCurrentAnalysis,
  getProject,
  getScript,
  listScripts,
  listTrackerItems,
  updateTrackerItemState,
  type AnalysisJob,
  type Finding,
  type Project,
  type QuestionAnswer,
  type ScriptFile,
  type Script,
  type ScriptCreate,
  type ScriptSummary,
  type TrackerItem,
  type TrackerState,
} from "../api/client";
import { DEMO_PROJECT } from "../app/demo";
import { pollUntilSettled } from "../features/analysis/model";
import { attempt, fail, failureMessage, succeed, type Outcome } from "./outcome";
import { jurisdictionFor, rememberProject } from "./recentProjects";
import { useServerMode } from "./ServerModeContext";

export interface ProjectContextValue {
  projectId: string;
  /** Null until the project GET answers, and after it fails. Views fall
   * back to `projectId`, which is the one thing they always know. */
  project: Project | null;
  projectError: string | null;
  jurisdictionCode: string;
  /** Every stored version of this project's script, newest first. */
  scripts: ScriptSummary[] | null;
  /** The newest stored script version, with its scenes and findings. */
  analysis: Script | null;
  analysisError: string | null;
  /** The queued analysis while one is running in this session. */
  job: AnalysisJob | null;
  /** Null until the mount GET answers; `[]` when no analysis ever ran. */
  tracker: TrackerItem[] | null;
  trackerError: string | null;
  pendingItemIds: ReadonlySet<string>;
  selectedItemId: string | null;
  refreshTracker: () => Promise<void>;
  refreshMetadata?: () => Promise<void>;
  runAnalysis: (request: ScriptCreate) => Promise<Outcome<Script>>;
  changeState: (itemId: string, state: TrackerState) => Promise<Outcome<TrackerItem>>;
  draftEmail: (itemId: string) => Promise<Outcome<TrackerItem>>;
  notify: (itemId: string, reason: string) => Promise<Outcome<TrackerItem>>;
  /** Stores a screenplay PDF and answers its `gs://` URI, which
   * `runAnalysis` then takes. Upload and analysis are two steps so a
   * re-run of the same upload costs no second transfer. */
  uploadScript: (file: File) => Promise<Outcome<ScriptFile>>;
  ask: (question: string) => Promise<Outcome<QuestionAnswer>>;
  setJurisdiction: (code: string) => void;
  selectItem: (itemId: string | null) => void;
  findingFor: (itemId: string) => Finding | null;
  itemFor: (findingId: string) => TrackerItem | null;
}

const GENERIC_TRACKER_ERROR = "The tracker request failed unexpectedly.";
const GENERIC_PROJECT_ERROR = "The project request failed unexpectedly.";
const GENERIC_SCRIPT_ERROR = "The script request failed unexpectedly.";
const GENERIC_ANALYZE_ERROR = "The analyze request failed unexpectedly.";
const GENERIC_MUTATION_ERROR = "The tracker update failed unexpectedly.";
const GENERIC_UPLOAD_ERROR = "The screenplay could not be stored.";
const GENERIC_QUESTION_ERROR = "The question request failed unexpectedly.";

const ProjectContext = createContext<ProjectContextValue | null>(null);

export interface ProjectProviderProps {
  projectId: string;
  /** Test seam: a script already loaded, as if the mount GET had answered. */
  initialAnalysis?: Script | null;
  /** Test seam: how the analysis poll waits between reads. Production
   * passes nothing and gets a real timer; a test passes a no-op and drives
   * the same code without spending the policy's seconds. */
  pollWait?: (ms: number) => Promise<void>;
  children: ReactNode;
}

function replaceItem(items: TrackerItem[], itemId: string, updated: TrackerItem): TrackerItem[] {
  return items.map((item) => (item.item_id === itemId ? updated : item));
}

function withId(ids: ReadonlySet<string>, itemId: string): Set<string> {
  return new Set(ids).add(itemId);
}

function withoutId(ids: ReadonlySet<string>, itemId: string): Set<string> {
  const next = new Set(ids);
  next.delete(itemId);
  return next;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * The project-scoped data layer and, with `ServerModeProvider`, the only
 * caller of `client.ts` outside tests. Views read state and call actions;
 * they never fetch. Mutations replace exactly the row they targeted from
 * the response the server sent back: never optimistic, never a refetch of
 * the whole list (CP-054). Mount the provider with `key={projectId}` so a
 * change of project starts from a clean slate.
 *
 * Three reads run on mount, each independent: the project, the newest
 * stored script, and the tracker. One failing leaves the other two on
 * screen, because a missing title is no reason to hide the findings.
 */
export function ProjectProvider({
  projectId,
  initialAnalysis = null,
  pollWait = sleep,
  children,
}: ProjectProviderProps): ReactElement {
  const [project, setProject] = useState<Project | null>(null);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [jurisdictionCode, setJurisdiction] = useState(
    () => jurisdictionFor(projectId) ?? DEMO_PROJECT.jurisdictionCode,
  );
  const [scripts, setScripts] = useState<ScriptSummary[] | null>(null);
  const [analysis, setAnalysis] = useState<Script | null>(initialAnalysis);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [tracker, setTracker] = useState<TrackerItem[] | null>(null);
  const [trackerError, setTrackerError] = useState<string | null>(null);
  const [pendingItemIds, setPendingItemIds] = useState<ReadonlySet<string>>(new Set());
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  const mode = useServerMode();
  const loadTracker = useCallback(
    async (isCancelled: () => boolean): Promise<void> => {
      try {
        const items = await listTrackerItems(projectId);
        if (!isCancelled()) {
          setTracker(items);
          setTrackerError(null);
        }
      } catch (thrown) {
        if (!isCancelled()) {
          setTrackerError(failureMessage(thrown, GENERIC_TRACKER_ERROR));
        }
      }
    },
    [projectId],
  );

  useEffect(() => {
    let cancelled = false;
    void loadTracker(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadTracker]);

  useEffect(() => {
    let cancelled = false;
    getProject(projectId)
      .then((found) => {
        if (!cancelled) {
          setProject(found);
          setProjectError(null);
          setJurisdiction(found.jurisdiction_code);
        }
      })
      .catch((thrown: unknown) => {
        if (!cancelled) {
          setProjectError(failureMessage(thrown, GENERIC_PROJECT_ERROR));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (mode !== "live") return;
    let cancelled = false;
    void (async () => {
      const queued = await getCurrentAnalysis(projectId);
      if (!queued || cancelled) return;
      setJob(queued);
      if (queued.state !== "QUEUED" && queued.state !== "RUNNING") return;
      const result = await pollUntilSettled(queued, {
        readJob: async () => {
          if (cancelled) throw new Error("Project changed");
          const current = await getAnalysis(projectId, queued.analysis_id);
          if (!cancelled) setJob(current);
          return current;
        }, wait: pollWait, now: () => Date.now(),
      });
      if (cancelled) return;
      if (result.kind === "ready") {
        const completed = await getScript(projectId, result.scriptId);
        if (!cancelled) {
          setAnalysis(completed); setAnalysisError(null);
          void loadTracker(() => cancelled);
        }
      } else setAnalysisError(result.message);
    })().catch(() => { /* Existing script remains usable when polling is unavailable. */ });
    return () => { cancelled = true; };
  }, [projectId, mode, pollWait, loadTracker]);

  // The newest stored version, so a finding survives a reload. `listScripts`
  // answers newest first, and an empty list means no analysis ever ran --
  // which is not an error and leaves `analysis` null.
  useEffect(() => {
    let cancelled = false;
    listScripts(projectId)
      .then(async (versions) => {
        if (cancelled) {
          return;
        }
        setScripts(versions);
        if (versions.length === 0) {
          return;
        }
        const newest = await getScript(projectId, versions[0].script_id);
        if (!cancelled) {
          setAnalysis(newest);
          setAnalysisError(null);
        }
      })
      .catch((thrown: unknown) => {
        if (!cancelled) {
          setAnalysisError(failureMessage(thrown, GENERIC_SCRIPT_ERROR));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // A deep link is a real visit, so the mount remembers it with the code
  // the provider started from (the remembered one, else the demo default).
  useEffect(() => {
    rememberProject(projectId, jurisdictionFor(projectId) ?? DEMO_PROJECT.jurisdictionCode);
  }, [projectId]);

  const refreshTracker = useCallback(() => loadTracker(() => false), [loadTracker]);
  const refreshMetadata = useCallback(async () => {
    try { const found = await getProject(projectId); setProject(found); setProjectError(null); }
    catch { setProjectError("Project details could not be refreshed."); }
  }, [projectId]);

  /**
   * Queues the analysis, then polls the job the 202 handed back until it
   * settles, then reads the script it produced. Every step reports through
   * one `Outcome`, so a view shows one sentence whether the queue was
   * refused, the run failed, or the wait ran out.
   */
  const runAnalysis = useCallback(
    async (request: ScriptCreate): Promise<Outcome<Script>> => {
      const queued = await attempt(
        () => createScript(projectId, request),
        GENERIC_ANALYZE_ERROR,
      );
      if (!queued.ok) {
        return queued;
      }
      setJob(queued.value);
      const analysisId = queued.value.analysis_id;
      const settled = await attempt(
        () =>
          pollUntilSettled(queued.value, {
            readJob: async () => {
              const current = await getAnalysis(projectId, analysisId);
              setJob(current);
              return current;
            },
            wait: pollWait,
            now: () => Date.now(),
          }),
        GENERIC_ANALYZE_ERROR,
      );
      if (!settled.ok) {
        return settled;
      }
      const step = settled.value;
      if (step.kind !== "ready") {
        return fail(step.message);
      }
      const script = await attempt(
        () => getScript(projectId, step.scriptId),
        GENERIC_SCRIPT_ERROR,
      );
      if (script.ok) {
        setAnalysis(script.value);
        setAnalysisError(null);
        setJurisdiction(script.value.jurisdiction_code);
        void loadTracker(() => false);
        void listScripts(projectId)
          .then(setScripts)
          .catch(() => {
            // The version list is a detail; the script itself is on screen.
          });
        return succeed(script.value);
      }
      return script;
    },
    [projectId, loadTracker, pollWait],
  );

  const runMutation = useCallback(
    async (
      itemId: string,
      request: () => Promise<TrackerItem>,
    ): Promise<Outcome<TrackerItem>> => {
      setPendingItemIds((current) => withId(current, itemId));
      try {
        const outcome = await attempt(request, GENERIC_MUTATION_ERROR);
        if (outcome.ok) {
          setTracker((current) =>
            current === null ? current : replaceItem(current, itemId, outcome.value),
          );
        }
        return outcome;
      } finally {
        setPendingItemIds((current) => withoutId(current, itemId));
      }
    },
    [],
  );

  const changeState = useCallback(
    (itemId: string, state: TrackerState) =>
      runMutation(itemId, () => updateTrackerItemState(projectId, itemId, state)),
    [runMutation, projectId],
  );

  const draftEmail = useCallback(
    (itemId: string) =>
      runMutation(itemId, () => createTrackerItemEmailDraft(projectId, itemId)),
    [runMutation, projectId],
  );

  const notify = useCallback(
    (itemId: string, reason: string) =>
      runMutation(itemId, () =>
        createTrackerItemNotification(projectId, itemId, reason),
      ),
    [runMutation, projectId],
  );

  const uploadScript = useCallback(
    (file: File) =>
      attempt(() => uploadScriptFile(projectId, file), GENERIC_UPLOAD_ERROR),
    [projectId],
  );

  const ask = useCallback(
    (question: string) =>
      attempt(
        () => askProjectQuestion(projectId, jurisdictionCode, question),
        GENERIC_QUESTION_ERROR,
      ),
    [projectId, jurisdictionCode],
  );

  const itemFor = useCallback(
    (findingId: string): TrackerItem | null =>
      tracker?.find((item) => item.finding_id === findingId) ?? null,
    [tracker],
  );

  const findingFor = useCallback(
    (itemId: string): Finding | null => {
      const item = tracker?.find((candidate) => candidate.item_id === itemId);
      if (item === undefined || analysis === null) {
        return null;
      }
      return analysis.findings.find((finding) => finding.finding_id === item.finding_id) ?? null;
    },
    [analysis, tracker],
  );

  const value = useMemo<ProjectContextValue>(
    () => ({
      projectId,
      project,
      projectError,
      jurisdictionCode,
      scripts,
      analysis,
      analysisError,
      job,
      tracker,
      trackerError,
      pendingItemIds,
      selectedItemId,
      refreshTracker,
      refreshMetadata,
      runAnalysis,
      uploadScript,
      changeState,
      draftEmail,
      notify,
      ask,
      setJurisdiction,
      selectItem: setSelectedItemId,
      findingFor,
      itemFor,
    }),
    [
      projectId,
      project,
      projectError,
      jurisdictionCode,
      scripts,
      analysis,
      analysisError,
      job,
      tracker,
      trackerError,
      pendingItemIds,
      selectedItemId,
      refreshTracker,
      refreshMetadata,
      runAnalysis,
      uploadScript,
      changeState,
      draftEmail,
      notify,
      ask,
      findingFor,
      itemFor,
    ],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
  const value = useContext(ProjectContext);
  if (value === null) {
    throw new Error("useProject must be called under a ProjectProvider");
  }
  return value;
}
