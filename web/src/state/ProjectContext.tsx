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
  fetchTracker,
  patchTrackerState,
  postAnalyze,
  postQuestion,
  postTrackerAction,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type Finding,
  type QuestionResponse,
  type TrackerItem,
  type TrackerState,
} from "../api/client";
import { DEMO_PROJECT } from "../app/demo";
import { attempt, failureMessage, type Outcome } from "./outcome";
import { jurisdictionFor, rememberProject } from "./recentProjects";

export interface ProjectContextValue {
  projectId: string;
  jurisdictionCode: string;
  /** The analysis a POST returned in this session; null after a reload. */
  analysis: AnalyzeResponse | null;
  /** Null until the mount GET answers; `[]` when no analysis ever ran. */
  tracker: TrackerItem[] | null;
  trackerError: string | null;
  pendingItemIds: ReadonlySet<string>;
  selectedItemId: string | null;
  refreshTracker: () => Promise<void>;
  runAnalysis: (request: AnalyzeRequest) => Promise<Outcome<AnalyzeResponse>>;
  changeState: (itemId: string, state: TrackerState) => Promise<Outcome<TrackerItem>>;
  draftEmail: (itemId: string) => Promise<Outcome<TrackerItem>>;
  notify: (itemId: string) => Promise<Outcome<TrackerItem>>;
  ask: (question: string) => Promise<Outcome<QuestionResponse>>;
  setJurisdiction: (code: string) => void;
  selectItem: (itemId: string | null) => void;
  findingFor: (itemId: string) => Finding | null;
  itemFor: (findingId: string) => TrackerItem | null;
}

const GENERIC_TRACKER_ERROR = "The tracker request failed unexpectedly.";
const GENERIC_ANALYZE_ERROR = "The analyze request failed unexpectedly.";
const GENERIC_MUTATION_ERROR = "The tracker update failed unexpectedly.";
const GENERIC_QUESTION_ERROR = "The question request failed unexpectedly.";

const ProjectContext = createContext<ProjectContextValue | null>(null);

export interface ProjectProviderProps {
  projectId: string;
  /** Test seam: an analysis already in session, as if a POST had run. */
  initialAnalysis?: AnalyzeResponse | null;
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

/**
 * The project-scoped data layer and, with `ServerModeProvider`, the only
 * caller of `client.ts` outside tests. Views read state and call actions;
 * they never fetch. Mutations replace exactly the row they targeted from
 * the response the server sent back: never optimistic, never a refetch of
 * the whole list (CP-054). Mount the provider with `key={projectId}` so a
 * change of project starts from a clean slate.
 */
export function ProjectProvider({
  projectId,
  initialAnalysis = null,
  children,
}: ProjectProviderProps): ReactElement {
  const [jurisdictionCode, setJurisdiction] = useState(
    () => jurisdictionFor(projectId) ?? DEMO_PROJECT.jurisdictionCode,
  );
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(initialAnalysis);
  const [tracker, setTracker] = useState<TrackerItem[] | null>(null);
  const [trackerError, setTrackerError] = useState<string | null>(null);
  const [pendingItemIds, setPendingItemIds] = useState<ReadonlySet<string>>(new Set());
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  const loadTracker = useCallback(
    async (isCancelled: () => boolean): Promise<void> => {
      try {
        const items = await fetchTracker(projectId);
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

  // A deep link is a real visit, so the mount remembers it with the code
  // the provider started from (the remembered one, else the demo default).
  useEffect(() => {
    rememberProject(projectId, jurisdictionFor(projectId) ?? DEMO_PROJECT.jurisdictionCode);
  }, [projectId]);

  const refreshTracker = useCallback(() => loadTracker(() => false), [loadTracker]);

  const runAnalysis = useCallback(
    async (request: AnalyzeRequest): Promise<Outcome<AnalyzeResponse>> => {
      const outcome = await attempt(
        () => postAnalyze(projectId, request),
        GENERIC_ANALYZE_ERROR,
      );
      if (outcome.ok) {
        setAnalysis(outcome.value);
        setTracker(outcome.value.tracker_items);
        setTrackerError(null);
        setJurisdiction(outcome.value.jurisdiction_code);
      }
      return outcome;
    },
    [projectId],
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
      runMutation(itemId, () => patchTrackerState(itemId, state)),
    [runMutation],
  );

  const draftEmail = useCallback(
    (itemId: string) => runMutation(itemId, () => postTrackerAction(itemId, "draft_email")),
    [runMutation],
  );

  const notify = useCallback(
    (itemId: string) => runMutation(itemId, () => postTrackerAction(itemId, "notify")),
    [runMutation],
  );

  const ask = useCallback(
    (question: string) =>
      attempt(
        () => postQuestion(projectId, jurisdictionCode, question),
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
      jurisdictionCode,
      analysis,
      tracker,
      trackerError,
      pendingItemIds,
      selectedItemId,
      refreshTracker,
      runAnalysis,
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
      jurisdictionCode,
      analysis,
      tracker,
      trackerError,
      pendingItemIds,
      selectedItemId,
      refreshTracker,
      runAnalysis,
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
