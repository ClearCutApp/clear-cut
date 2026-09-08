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
  clearance_conditions?: string;
  due_date?: string;
  assignee_id?: string;
  evidence_file_ids?: string[];
  rights_holder_citations?: Citation[];
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
  revision_id?: string;
  revision_draft_version?: number;
  scene_anchors?: Array<{scene_number: number; scene_id: string; blocks: Array<{block_id: string; start: number; end: number; page_start: number; page_end: number}>}>;
  clearance_bindings?: Record<string, {revision_id?: string; present: boolean; scene_ids?: string[]}>;
  settings_version?: number | null;
  coverage_gaps?: Array<{stage: string; code: string}>;
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
  file_id?: string;
  gcs_uri: string;
  filename: string;
  size_bytes: number;
  content_type: string;
}

export interface LegacyScriptCreate {
  file_id?: string;
  gcs_uri: string;
  version: number;
  jurisdiction_code: string;
}
export type ScriptCreate = LegacyScriptCreate | { revision_id: string; jurisdiction_code: string };

/** `SUCCEEDED` and `FAILED` are terminal; a later run is a new analysis. */
export type AnalysisState = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";

export interface AnalysisJob {
  revision_id?: string;
  stage?: string;
  attempt?: number;
  cancel_requested?: boolean;
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

export function reconfirmClearance(projectId: string, itemId: string, expectedVersion: number, revisionId: string): Promise<TrackerItem> {
  return requestJson(`${trackerItemPath(projectId, itemId)}/reconfirmation`, jsonRequest("POST", {
    expected_version: expectedVersion, revision_id: revisionId, acknowledged: true,
  }));
}

export interface ClearanceCounts {
  total_retained: number;
  confirmed_cleared: number;
  needs_review: number;
  blocked: number;
  in_progress: number;
  present: number;
  not_detected: number;
  unknown_binding: number;
  confirmed_cleared_percent: number;
}
export interface ReportSnapshotContext {
  analysis_id: string;
  revision_id: string;
  expected_generation: string;
  expected_epoch: number;
  counts: ClearanceCounts;
}
export interface ClearanceReport {
  report_id: string;
  project_id: string;
  analysis_id: string;
  revision_id: string;
  generation_id: string;
  clearance_epoch: number;
  created_at: string;
  created_by: string;
  language: "en" | "es";
  counts: ClearanceCounts;
  formula_version: string;
  template_version: string;
}
export interface ReportPage { reports: ClearanceReport[]; next_before: string | null; }
export interface ActivityEvent {
  event_id: string; kind: string; occurred_at: string; source_version: number;
  payload: {
    item_id?: string; revision_id?: string; state?: TrackerState; needs_review?: boolean;
    item_count?: number; counts?: Partial<ClearanceCounts>; file_id?: string;
  };
}
export interface ActivityPage {
  configured: boolean; events: ActivityEvent[]; trends: ActivityEvent[]; next_before: string | null;
}
export function getProjectActivity(projectId: string, before?: string): Promise<ActivityPage> {
  return requestJson(`${projectPath(projectId)}/activity${before ? `?before=${encodeURIComponent(before)}` : ""}`);
}
export function getReportContext(projectId: string): Promise<{ configured: boolean; snapshot: ReportSnapshotContext | null }> {
  return requestJson(`${projectPath(projectId)}/reports/context`);
}
export function listReports(projectId: string, before?: string): Promise<ReportPage> {
  return requestJson(`${projectPath(projectId)}/reports${before ? `?before=${encodeURIComponent(before)}` : ""}`);
}
export function createReport(projectId: string, snapshot: ReportSnapshotContext, language: "en" | "es"): Promise<ClearanceReport> {
  const { counts: _counts, ...identity } = snapshot;
  return requestJson(`${projectPath(projectId)}/reports`, jsonRequest("POST", { ...identity, language }));
}
export async function downloadReport(projectId: string, reportId: string, format: "pdf" | "csv"): Promise<Blob> {
  return (await requestResponse(`${projectPath(projectId)}/reports/${encodeURIComponent(reportId)}/download?format=${format}`)).blob();
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

export function cancelAnalysis(projectId: string, analysisId: string): Promise<AnalysisJob> {
  return requestJson<AnalysisJob>(`${projectPath(projectId)}/analyses/${encodeURIComponent(analysisId)}/cancellation`, jsonRequest("POST", {}));
}

export async function getCurrentAnalysis(projectId: string): Promise<AnalysisJob | null> {
  const value = await requestJson<AnalysisJob | {analysis: null}>(`${projectPath(projectId)}/analyses/current`);
  return "analysis_id" in value ? value : null;
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
  expectedVersion: number,
): Promise<TrackerItem> {
  return requestJson<TrackerItem>(
    trackerItemPath(projectId, itemId),
    jsonRequest("PATCH", { state, expected_version: expectedVersion }),
  );
}

/** Fills the outreach template and stores it on the item. The system never
 * sends it: a producer copies the draft and sends it themselves. */
export function createTrackerItemEmailDraft(
  projectId: string,
  itemId: string,
  expectedVersion: number,
): Promise<TrackerItem> {
  return requestJson<TrackerItem>(
    `${trackerItemPath(projectId, itemId)}/email-drafts`,
    jsonRequest("POST", { expected_version: expectedVersion }),
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


export interface ScreenplayDocument { type: "doc"; content: ScreenplayBlock[]; }
export interface ScreenplayBlock {
  type: "paragraph";
  attrs: { blockId: string; sceneId: string; kind: string };
  content?: { type: "text" | "hardBreak"; text?: string; marks?: { type: string }[] }[];
}
export interface ScreenplayDraft { project_id: string; version: number; document: ScreenplayDocument | null; updated_at: string; updated_by: string; }
export interface ScreenplayRevision { revision_id: string; project_id: string; draft_version: number; sha256: string; created_at: string; created_by: string; document?: ScreenplayDocument; }
export interface RevisionPage { revisions: ScreenplayRevision[]; next_before_version: number | null; }
export function getDraft(projectId: string): Promise<ScreenplayDraft> {
  return requestJson(`${projectPath(projectId)}/draft`);
}
export function saveDraft(projectId: string, expectedVersion: number, document: ScreenplayDocument): Promise<ScreenplayDraft> {
  return requestJson(`${projectPath(projectId)}/draft`, jsonRequest("PUT", { expected_version: expectedVersion, document }));
}
export function freezeRevision(projectId: string, expectedVersion: number): Promise<ScreenplayRevision> {
  return requestJson(`${projectPath(projectId)}/revisions`, jsonRequest("POST", { expected_version: expectedVersion }));
}
export function listRevisions(projectId: string, beforeVersion?: number): Promise<RevisionPage> {
  return requestJson(`${projectPath(projectId)}/revisions${beforeVersion ? `?before_version=${String(beforeVersion)}` : ""}`);
}
export function getRevision(projectId: string, revisionId: string): Promise<ScreenplayRevision> {
  return requestJson(`${projectPath(projectId)}/revisions/${encodeURIComponent(revisionId)}`);
}


export type SpeechLanguage = "en-US" | "es-419" | "es-ES";
export interface Transcription { text: string; language: SpeechLanguage; }
export function transcribeQuestion(projectId: string, audio: Blob, language: SpeechLanguage, signal?: AbortSignal): Promise<Transcription> {
  const body = new FormData();
  body.append("audio", audio, "question");
  body.append("language", language);
  return requestJson(`${projectPath(projectId)}/transcriptions`, { method: "POST", body, signal });
}


export interface ProjectDocument { file_id: string; organization_id: string; project_id: string; filename: string; content_type: string; size_bytes: number; sha256: string; kind: string; created_by: string; created_at: string; revision_id: string; }
export interface DocumentPage { documents: ProjectDocument[]; next_before: string | null; }
export function listDocuments(projectId: string, before?: string): Promise<DocumentPage> {
  return requestJson(`${projectPath(projectId)}/documents${before ? `?before=${encodeURIComponent(before)}` : ""}`);
}
export function uploadDocument(projectId: string, file: File): Promise<ProjectDocument> {
  const body = new FormData(); body.append("file", file);
  return requestJson(`${projectPath(projectId)}/documents`, { method: "POST", body });
}
export async function downloadDocument(projectId: string, fileId: string): Promise<Blob> {
  const response = await requestResponse(`${projectPath(projectId)}/documents/${encodeURIComponent(fileId)}`);
  return response.blob();
}
export interface ScreenplayImportResult { draft: ScreenplayDraft; original: ProjectDocument; warnings: string[]; }
export function importScreenplay(projectId: string, file: File, expectedVersion: number): Promise<ScreenplayImportResult> {
  const body = new FormData(); body.append("file", file); body.append("expected_version", String(expectedVersion));
  return requestJson(`${projectPath(projectId)}/imports`, { method: "POST", body });
}
export async function exportScreenplay(projectId: string, revisionId: string, format: "pdf" | "fdx"): Promise<Blob> {
  const response = await requestResponse(`${projectPath(projectId)}/revisions/${encodeURIComponent(revisionId)}/exports/${format}`);
  return response.blob();
}

export interface TrackerAuditEvent {
  event_id: string;
  actor: string;
  version: number;
  previous_version: number;
  at: string;
  item: TrackerItem;
}

export function listTrackerItemHistory(projectId: string, itemId: string, beforeVersion?: number): Promise<TrackerAuditEvent[]> {
  const query = beforeVersion === undefined ? "" : `?before_version=${beforeVersion}`;
  return requestJson<TrackerAuditEvent[]>(`${trackerItemPath(projectId, itemId)}/history${query}`);
}

export interface ClearanceDetails {
  note: string;
  clearance_conditions: string;
  due_date: string;
  assignee_id: string;
  evidence_file_ids: string[];
  draft_email: string | null;
}

export function updateClearanceDetails(projectId: string, itemId: string, expectedVersion: number, details: ClearanceDetails): Promise<TrackerItem> {
  return requestJson<TrackerItem>(`${trackerItemPath(projectId, itemId)}/details`, jsonRequest("PUT", { ...details, expected_version: expectedVersion }));
}

export async function downloadPermissionRequest(projectId: string, itemId: string, version: number, format: "pdf" | "txt"): Promise<Blob> {
  return (await requestResponse(`${trackerItemPath(projectId, itemId)}/permission-request?version=${version}&format=${format}`)).blob();
}

export interface ProjectNotification {
  notification_id: string; item_id: string; item_version: number;
  actor: string; reason: string; created_at: string; read: boolean;
  delivery: "in_app_only" | "queued" | "pending" | "delivering" | "delivered" | "blocked" | "failed";
}
export interface NotificationPage {
  configured: boolean; notifications: ProjectNotification[]; next_cursor: string | null;
}
export function getProjectNotifications(projectId: string, before?: string): Promise<NotificationPage> {
  return requestJson(`${projectPath(projectId)}/notifications${before ? `?before=${encodeURIComponent(before)}` : ""}`);
}
export function readProjectNotification(projectId: string, notificationId: string): Promise<{ read: boolean }> {
  return requestJson(`${projectPath(projectId)}/notifications/${encodeURIComponent(notificationId)}/read`, { method: "POST" });
}

