/**
 * The one module that names an API path (SDD Section 5, ADR 0009). Every
 * request/response shape here mirrors SDD Section 4 field for field, so a
 * backend shape change breaks this file's build instead of a demo.
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

export interface ScriptViewResponse {
  script_id: string;
  project_id: string;
  version: number;
  jurisdiction_code: string;
  scenes: Scene[];
  findings: Finding[];
}

export interface TrackerContact {
  name: string;
  email: string;
}

export interface TrackerItem {
  item_id: string;
  finding_id: string;
  scene_numbers: number[];
  state: TrackerState;
  needs_review: boolean;
  required_document: string;
  contact: TrackerContact | null;
  litigation_posture: string | null;
  draft_email: string | null;
  note: string | null;
  updated_at: string;
  version: number;
}

export type TrackerResponse = TrackerItem[];

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  return (await response.json()) as T;
}

export function fetchScript(scriptId: string): Promise<ScriptViewResponse> {
  return requestJson<ScriptViewResponse>(`/api/scripts/${scriptId}`);
}

export function fetchTracker(projectId: string): Promise<TrackerResponse> {
  return requestJson<TrackerResponse>(
    `/api/tracker?project_id=${projectId}`,
  );
}
