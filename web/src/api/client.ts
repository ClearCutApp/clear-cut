/**
 * The one module that names an API path (SDD Section 5, ADR 0009). Every
 * request/response shape here mirrors `adapters/http/routes.py`'s
 * serializers field for field, so a backend shape change breaks this
 * file's build instead of a demo.
 */

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type Category =
  | "INDUSTRIAL_PROPERTY"
  | "COPYRIGHT_WORKS"
  | "PERSONALITY_IMAGE"
  | "INTEGRATED_VISUAL"
  | "LOCATIONS_PERMITS"
  | "SPECIAL_SYMBOLS"
  | "CONTINUITY"
  | "POLICY";

export type NerLabel =
  | "BRAND"
  | "MUSIC_EXISTING"
  | "MUSIC_ORIGINAL"
  | "ART_LIT"
  | "MEDIA_AV"
  | "TALENT_CHARACTER"
  | "REAL_PERSON"
  | "PROPS_DESIGN"
  | "LOCATION_PRIV"
  | "LOCATION_PUB"
  | "SPECIAL_SYMBOL";

export type TrackerState = "BLOCKED" | "IN_PROGRESS" | "CLEARED";

// The only two actions `_build_action` (routes.py:138-148) accepts.
// `generate_document` and `stakeholder_link` are Backlog-ruled
// unimplemented and 500 on the server -- admitting them here would let a
// component compile its way into a guaranteed server error.
export type TrackerAction = "draft_email" | "notify";

export interface Citation {
  uri: string;
  title: string;
  snippet: string;
}

export interface Scene {
  number: number;
  heading: string;
  page_start: number;
  page_end: number;
  text: string;
  content_hash: string;
}

export interface Finding {
  finding_id: string;
  scene_number: number;
  page: number;
  raw_text: string;
  category: Category;
  ner_label: NerLabel | null;
  risk_level: RiskLevel;
  required_document: string;
  citations: Citation[];
  contradicts: string | null;
}

export interface TrackerItem {
  item_id: string;
  project_id: string;
  finding_id: string;
  scene_numbers: number[];
  state: TrackerState;
  needs_review: boolean;
  required_document: string;
  contact: string;
  litigation_posture: string;
  draft_email: string | null;
  note: string;
  updated_at: string;
  version: number;
}

export type TrackerResponse = TrackerItem[];

export interface AnalyzeResponse {
  script_id: string;
  project_id: string;
  version: number;
  gcs_uri: string;
  jurisdiction_code: string;
  scenes: Scene[];
  findings: Finding[];
  tracker_items: TrackerItem[];
}

/** `project_id` is absent on purpose: it is a path segment since the REST
 * rename, so it names the collection being written to rather than a field of
 * the thing written. `postAnalyze` takes it as its own argument. */
export interface AnalyzeRequest {
  gcs_uri: string;
  version: number;
  jurisdiction_code: string;
}

export interface BibleFact {
  fact_id: string;
  kind: "LORE" | "POLICY";
  text: string;
  source: string;
}

export interface QuestionResponse {
  text: string;
  facts: BibleFact[];
  citations: Citation[];
}

/** What `CLEARCUT_MODE` the server is serving under. `mock` means every
 * scene, finding and tracker item came from `adapters/demo/scenario.py`
 * rather than from a real analysis. */
export type ServerMode = "mock" | "live";

export interface HealthResponse {
  mode: ServerMode;
}

/** The Swagger UI the server mounts (built routes only). Exported so the
 * sidebar can link to it without spelling a path of its own. */
export const API_DOCS_PATH = "/api/docs";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "response body was not valid JSON");
  }
}

function jsonRequest(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function fetchTracker(projectId: string): Promise<TrackerResponse> {
  return requestJson<TrackerResponse>(
    `/api/projects/${projectId}/tracker-items`,
  );
}

export function postAnalyze(
  projectId: string,
  request: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  return requestJson<AnalyzeResponse>(
    `/api/projects/${projectId}/scripts`,
    jsonRequest("POST", request),
  );
}

export function patchTrackerState(
  itemId: string,
  state: TrackerState,
): Promise<TrackerItem> {
  return requestJson<TrackerItem>(
    `/api/tracker-items/${itemId}`,
    jsonRequest("PATCH", { state }),
  );
}

export function postTrackerAction(
  itemId: string,
  action: TrackerAction,
  reason?: string,
): Promise<TrackerItem> {
  const body = reason === undefined ? { action } : { action, reason };
  return requestJson<TrackerItem>(
    `/api/tracker-items/${itemId}/actions`,
    jsonRequest("POST", body),
  );
}

export function postQuestion(
  projectId: string,
  jurisdictionCode: string,
  question: string,
): Promise<QuestionResponse> {
  return requestJson<QuestionResponse>(
    `/api/projects/${projectId}/questions`,
    jsonRequest("POST", {
      jurisdiction_code: jurisdictionCode,
      question,
    }),
  );
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health");
}
