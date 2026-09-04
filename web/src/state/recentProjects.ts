/**
 * The per-browser list of projects the reader opened, most recent first.
 * There is no project resource on the server (Missing API registry), so
 * this list is the only "projects" the landing view can show, and it says
 * so there. Written on Open and on `ProjectProvider` mount, because a deep
 * link is a real visit too.
 */
export const RECENT_PROJECTS_KEY = "clearcut.recentProjects";
export const RECENT_PROJECTS_LIMIT = 8;

export interface RecentProject {
  projectId: string;
  jurisdictionCode: string;
  openedAt: string;
}

function isRecentProject(value: unknown): value is RecentProject {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.projectId === "string" &&
    typeof candidate.jurisdictionCode === "string" &&
    typeof candidate.openedAt === "string"
  );
}

/** Whatever storage holds, or `[]` when it is absent, unreadable or not JSON. */
function readStorage(): unknown {
  try {
    const raw = localStorage.getItem(RECENT_PROJECTS_KEY);
    return raw === null ? [] : JSON.parse(raw);
  } catch {
    return [];
  }
}

export function readRecentProjects(): RecentProject[] {
  const parsed = readStorage();
  return Array.isArray(parsed) ? parsed.filter(isRecentProject) : [];
}

/** Puts `projectId` first, drops its older entry, and keeps the list capped. */
export function rememberProject(
  projectId: string,
  jurisdictionCode: string,
  openedAt: Date = new Date(),
): RecentProject[] {
  const entry: RecentProject = {
    projectId,
    jurisdictionCode,
    openedAt: openedAt.toISOString(),
  };
  const others = readRecentProjects().filter(
    (project) => project.projectId !== projectId,
  );
  const next = [entry, ...others].slice(0, RECENT_PROJECTS_LIMIT);
  try {
    localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify(next));
  } catch {
    // Storage can be full or disabled; the caller still gets the list.
  }
  return next;
}

export function jurisdictionFor(projectId: string): string | null {
  const match = readRecentProjects().find(
    (project) => project.projectId === projectId,
  );
  return match?.jurisdictionCode ?? null;
}
