/**
 * The one module that names an API path (SDD Section 5, ADR 0009). Every
 * type here mirrors `docs/api/openapi.yaml` field for field, and every
 * function is named after the operation id the contract gives it, so a
 * contract change breaks this file's build instead of a view.
 *
 * Two contract rules shape the whole surface:
 *
 * - Every record is reached through its project. There is no top-level
 *   tracker collection, so each tracker call takes a project id.
 * - Queueing an analysis answers 202 with a job, not a result. The caller
 *   polls the job; `features/analysis/model.ts` owns that timing.
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

export interface Jurisdiction {
  code: string;
  display_name: string;
}

export interface Project {
  project_id: string;
  title: string;
  jurisdiction_code: string;
  created_at: string;
}

export interface ProjectCreate {
  organization_id?: string;
  title: string;
  jurisdiction_code: string;
}

/** One finding's offsets in one scene's `text`, computed server-side so a
 * highlight is a position rather than a substring search (ADR 0015). */
export interface Span {
  scene_number: number;
  start: number;
  end: number;
  finding_id: string;
  risk: RiskLevel;
}

export interface Scene {
  number: number;
  heading: string;
  page_start: number;
  page_end: number;
  text: string;
  content_hash: string;
  spans: Span[];
}

/** Note `risk_level`, not `risk`: the finding carries the long name and
 * only `Span` carries the short one. */
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

/** One script version without its scenes or findings. */
export interface ScriptSummary {
  script_id: string;
  project_id: string;
  version: number;
  gcs_uri: string;
  jurisdiction_code: string;
  scene_count: number;
  finding_count: number;
}

export interface Script {
  script_id: string;
  project_id: string;
  version: number;
  gcs_uri: string;
  jurisdiction_code: string;
  scenes: Scene[];
  findings: Finding[];
}

/** `project_id` is absent on purpose: it is the collection in the path,
 * not a field of the thing written. */
/** One uploaded screenplay in Cloud Storage, before anything has parsed it.
 *
 * Upload and analysis are two steps on purpose: re-analysing the same upload
 * costs no second transfer, so `gcs_uri` is handed straight to `createScript`.
 */
export interface ScriptFile {
  gcs_uri: string;
  filename: string;
  size_bytes: number;
  content_type: string;
}

export interface ScriptCreate {
  gcs_uri: string;
  version: number;
  jurisdiction_code: string;
}

/** `SUCCEEDED` and `FAILED` are terminal; a later run is a new analysis. */
export type AnalysisState = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";

export interface AnalysisJob {
  analysis_id: string;
  project_id: string;
  script_id: string;
  state: AnalysisState;
  created_at: string;
  updated_at: string;
  /** Why the run failed. Empty in every state but `FAILED`. */
  error: string;
  version: number;
}

export interface BibleFact {
  fact_id: string;
  kind: "LORE" | "POLICY";
  text: string;
  source: string;
}

export interface QuestionAnswer {
  text: string;
  facts: BibleFact[];
  citations: Citation[];
}

/** What `CLEARCUT_MODE` the server is serving under. `mock` means every
 * scene, finding and tracker item came from `adapters/demo/scenario.py`
 * rather than from a real analysis. */
export type ServerMode = "mock" | "live";

export interface Health {
  mode: ServerMode;
}

/** The Swagger UI the server mounts. Exported so the sidebar can link to
 * it without spelling a path of its own. */
export const API_DOCS_PATH = "/api/docs";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** The sentence to show a producer for a failing response.
 *
 * Every failing response is contracted to carry `{"error": "<one sentence>"}`
 * (docs/api/openapi.yaml, the Error schema), written to be safe to display.
 * Handing the raw body to a component instead puts `{"error":"not found"}` on
 * the screen, braces and all, which is what shipped before this.
 *
 * Two fallbacks, because a failure is the worst moment to throw a second one:
 * a body that is not the contract's shape is shown as-is, since an unexpected
 * body is still better evidence than a generic apology, and an empty body
 * becomes the status, which is all that is known.
 */
function errorMessage(status: number, body: string): string {
  const trimmed = body.trim();
  if (trimmed === "") {
    return `the server returned ${String(status)}`;
  }
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "error" in parsed &&
      typeof (parsed as { error: unknown }).error === "string"
    ) {
      return (parsed as { error: string }).error;
    }
  } catch {
    // Not JSON. The raw body is the best evidence available.
  }
  return trimmed;
}

let identityToken: () => Promise<string | null> = async () => null;
export function setIdentityTokenProvider(provider: () => Promise<string | null>): void {
  identityToken = provider;
}

async function requestResponse(path: string, init?: RequestInit): Promise<Response> {
  const publicRead = path === "/api/health" || path === "/api/jurisdictions" || path === "/api/client-config";
  const token = publicRead ? null : await identityToken();
  let authenticated = init;
  if (token) {
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${token}`);
    authenticated = { ...init, headers };
  }
  const response = await fetch(path, authenticated);
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(response.status, await response.text()));
  }
  return response;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await requestResponse(path, init);
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

function projectPath(projectId: string): string {
  return `/api/projects/${encodeURIComponent(projectId)}`;
}

function trackerItemPath(projectId: string, itemId: string): string {
  return `${projectPath(projectId)}/tracker-items/${encodeURIComponent(itemId)}`;
}

// -------------------------------------------------------------- system --

export function getHealth(): Promise<Health> {
  return requestJson<Health>("/api/health");
}

export interface ClientConfig { apiKey: string; authDomain: string; projectId: string; appId: string; }
export function getClientConfig(): Promise<ClientConfig> {
  return requestJson<ClientConfig>("/api/client-config");
}
export interface IdentityContext { user_id: string; email: string; }
export interface Organization { organization_id: string; name: string; role: string; }
export type WorkspaceRole = "owner" | "admin" | "producer" | "writer" | "viewer";
export interface WorkspaceMember { user_id: string; email?: string; role: WorkspaceRole; active: boolean; version?: number; }
export interface WorkspaceInvitation { invitation_id: string; email: string; role: WorkspaceRole; state: string; version: number; expires_at: string; }
export interface ProjectMembers { organization_id: string; version: number; can_manage: boolean; can_edit?: boolean; members: { user_id: string; email: string; role: WorkspaceRole }[]; }
export interface ProductionLocation { country: string; location: string; }
export interface ProjectSettings { project_id: string; title: string; jurisdiction_code: string; version: number; locations: ProductionLocation[]; }
export function getWorkspaceMembers(organizationId: string): Promise<{ members: WorkspaceMember[] }> {
  return requestJson(`/api/organizations/${encodeURIComponent(organizationId)}/members`);
}
export function getWorkspaceInvitations(organizationId: string): Promise<{ invitations: WorkspaceInvitation[] }> {
  return requestJson(`/api/organizations/${encodeURIComponent(organizationId)}/invitations`);
}
export function inviteWorkspaceMember(organizationId: string, email: string, role: WorkspaceRole): Promise<{ invitation: WorkspaceInvitation; token: string }> {
  return requestJson(`/api/organizations/${encodeURIComponent(organizationId)}/invitations`, jsonRequest("POST", { email, role }));
}
export function revokeWorkspaceInvitation(organizationId: string, invitation: WorkspaceInvitation): Promise<unknown> {
  return requestJson(`/api/organizations/${encodeURIComponent(organizationId)}/invitations/${encodeURIComponent(invitation.invitation_id)}/revocation`,
    jsonRequest("POST", { expected_version: invitation.version }));
}
export function changeWorkspaceMember(organizationId: string, member: WorkspaceMember, role: WorkspaceRole, active: boolean): Promise<unknown> {
  return requestJson(`/api/organizations/${encodeURIComponent(organizationId)}/members/${encodeURIComponent(member.user_id)}`,
    jsonRequest("PATCH", { expected_version: member.version ?? 1, role, active }));
}
export function acceptWorkspaceInvitation(token: string): Promise<{ organization_id: string }> {
  return requestJson("/api/invitations/accept", jsonRequest("POST", { token }));
}
export function getProjectMembers(projectId: string): Promise<ProjectMembers> {
  return requestJson(`${projectPath(projectId)}/members`);
}
export function assignProjectMember(projectId: string, userId: string, role: WorkspaceRole | null, expectedVersion: number): Promise<unknown> {
  return requestJson(`${projectPath(projectId)}/members/${encodeURIComponent(userId)}`,
    jsonRequest("PATCH", { role, expected_version: expectedVersion }));
}
export function getProjectSettings(projectId: string): Promise<ProjectSettings> {
  return requestJson(`${projectPath(projectId)}/settings`);
}
export function saveProjectSettings(projectId: string, settings: ProjectSettings): Promise<ProjectSettings> {
  return requestJson(`${projectPath(projectId)}/settings`, jsonRequest("PUT", {
    expected_version: settings.version, title: settings.title,
    jurisdiction_code: settings.jurisdiction_code, locations: settings.locations,
  }));
}
export interface LocalResearchRecord {
  research_id: string; project_id: string; created_at: string; settings_version: number;
  location: ProductionLocation; question: string; text: string; citations: Citation[];
  status: "evidence_found" | "coverage_gap"; human_clearance: false; provider: string;
}
export function listLocalResearch(projectId: string): Promise<{ configured: boolean; research: LocalResearchRecord[] }> {
  return requestJson(`${projectPath(projectId)}/local-research`);
}
export function researchProductionLocation(projectId: string, settingsVersion: number, locationIndex: number, question: string): Promise<LocalResearchRecord> {
  return requestJson(`${projectPath(projectId)}/local-research`, jsonRequest("POST", {
    expected_settings_version: settingsVersion, location_index: locationIndex, question,
  }));
}
export function getIdentity(): Promise<IdentityContext> {
  return requestJson<IdentityContext>("/api/me");
}
export function listOrganizations(): Promise<Organization[]> {
  return requestJson<Organization[]>("/api/organizations");
}
export function createOrganization(name: string): Promise<Organization> {
  return requestJson<Organization>("/api/organizations", jsonRequest("POST", { name }));
}

// ------------------------------------------------------------ projects --

export function listJurisdictions(): Promise<Jurisdiction[]> {
  return requestJson<Jurisdiction[]>("/api/jurisdictions");
}

export function listProjects(): Promise<Project[]> {
  return requestJson<Project[]>("/api/projects");
}

export function createProject(request: ProjectCreate): Promise<Project> {
  return requestJson<Project>("/api/projects", jsonRequest("POST", request));
}

export function getProject(projectId: string): Promise<Project> {
  return requestJson<Project>(projectPath(projectId));
}

// ------------------------------------------------------------- scripts --

export function listScripts(projectId: string): Promise<ScriptSummary[]> {
  return requestJson<ScriptSummary[]>(`${projectPath(projectId)}/scripts`);
}

export function getScript(projectId: string, scriptId: string): Promise<Script> {
  return requestJson<Script>(
    `${projectPath(projectId)}/scripts/${encodeURIComponent(scriptId)}`,
  );
}

/**
 * Queues an analysis and answers 202 with the job, never the result. The
 * 202 also carries a `Location` header pointing at the job, which the body
 * already identifies by `project_id` and `analysis_id`; polling reads the
 * body so a proxy that drops the header cannot strand the caller.
 */
/** Writes a screenplay PDF to the intake bucket and returns its `gs://` URI.
 *
 * The body is a `FormData` with no `Content-Type` header, deliberately.
 * `multipart/form-data` is only parseable with the boundary that separates
 * its parts, the browser generates that boundary when it serialises the
 * body, and naming the type by hand overwrites the header without it -- so
 * the server receives a body it cannot split. This is why `jsonRequest` is
 * not reused here.
 */
export function uploadScriptFile(projectId: string, file: File): Promise<ScriptFile> {
  const body = new FormData();
  body.append("file", file);
  return requestJson<ScriptFile>(`/api/projects/${encodeURIComponent(projectId)}/script-files`, {
    method: "POST",
    body,
  });
}

export function createScript(
  projectId: string,
  request: ScriptCreate,
): Promise<AnalysisJob> {
  return requestJson<AnalysisJob>(
    `${projectPath(projectId)}/scripts`,
    jsonRequest("POST", request),
  );
}

export function getAnalysis(
  projectId: string,
  analysisId: string,
): Promise<AnalysisJob> {
  return requestJson<AnalysisJob>(
    `${projectPath(projectId)}/analyses/${encodeURIComponent(analysisId)}`,
  );
}

// ------------------------------------------------------------- tracker --

export function listTrackerItems(projectId: string): Promise<TrackerItem[]> {
  return requestJson<TrackerItem[]>(`${projectPath(projectId)}/tracker-items`);
}

export function getTrackerItem(
  projectId: string,
  itemId: string,
): Promise<TrackerItem> {
  return requestJson<TrackerItem>(trackerItemPath(projectId, itemId));
}

export function updateTrackerItemState(
  projectId: string,
  itemId: string,
  state: TrackerState,
): Promise<TrackerItem> {
  return requestJson<TrackerItem>(
    trackerItemPath(projectId, itemId),
    jsonRequest("PATCH", { state }),
  );
}

/** Fills the outreach template and stores it on the item. The system never
 * sends it: a producer copies the draft and sends it themselves. */
export function createTrackerItemEmailDraft(
  projectId: string,
  itemId: string,
): Promise<TrackerItem> {
  return requestJson<TrackerItem>(
    `${trackerItemPath(projectId, itemId)}/email-drafts`,
    { method: "POST" },
  );
}

export function createTrackerItemNotification(
  projectId: string,
  itemId: string,
  reason: string,
): Promise<TrackerItem> {
  return requestJson<TrackerItem>(
    `${trackerItemPath(projectId, itemId)}/notifications`,
    jsonRequest("POST", { reason }),
  );
}

// ----------------------------------------------------------- questions --

export function askProjectQuestion(
  projectId: string,
  jurisdictionCode: string,
  question: string,
): Promise<QuestionAnswer> {
  return requestJson<QuestionAnswer>(
    `${projectPath(projectId)}/questions`,
    jsonRequest("POST", { jurisdiction_code: jurisdictionCode, question }),
  );
}
export type SpeechLanguage = "en-US" | "es-419" | "es-ES";
export interface Transcription { text: string; language: SpeechLanguage; }
export function transcribeQuestion(projectId: string, audio: Blob, language: SpeechLanguage, signal?: AbortSignal): Promise<Transcription> {
  const body = new FormData();
  body.append("audio", audio, "question");
  body.append("language", language);
  return requestJson(`${projectPath(projectId)}/transcriptions`, { method: "POST", body, signal });
}


