import type { Project } from "../../api/client";

/**
 * What the projects landing can compute from `GET /api/projects`, and
 * nothing more. A project carries an id, a title, a jurisdiction and a
 * creation time; it carries no status, no team, no poster and no clearance
 * totals, so no number here is derived from one.
 */

const WEEK_MS = 7 * 24 * 60 * 60 * 1_000;

export interface ProjectMetrics {
  total: number;
  jurisdictions: number;
  addedThisWeek: number;
}

/** `ALL`, or a jurisdiction code the list actually contains. */
export type ProjectFilterValue = "ALL" | string;

export interface ProjectTab {
  value: ProjectFilterValue;
  code: string | null;
  count: number;
}

function parsedTime(iso: string): number | null {
  const time = new Date(iso).getTime();
  return Number.isNaN(time) ? null : time;
}

function jurisdictionsIn(projects: Project[]): string[] {
  return [...new Set(projects.map((project) => project.jurisdiction_code))].sort();
}

/** The three headline numbers, each read straight off the list. A stamp the
 * browser cannot parse counts toward the total and toward no week. */
export function projectMetrics(projects: Project[], now: Date = new Date()): ProjectMetrics {
  const since = now.getTime() - WEEK_MS;
  return {
    total: projects.length,
    jurisdictions: jurisdictionsIn(projects).length,
    addedThisWeek: projects.filter((project) => {
      const created = parsedTime(project.created_at);
      return created !== null && created >= since;
    }).length,
  };
}

/**
 * The filter row: All, then one tab per jurisdiction present, in code
 * order. The design's tabs are Active, Needs attention and Completed --
 * three statuses a project does not have -- so the axis the API does give
 * is the one drawn.
 */
export function projectTabs(projects: Project[]): ProjectTab[] {
  const perJurisdiction = jurisdictionsIn(projects).map((code) => ({
    value: code,
    code,
    count: projects.filter((project) => project.jurisdiction_code === code).length,
  }));
  return [{ value: "ALL", code: null, count: projects.length }, ...perJurisdiction];
}

export function applyProjectFilter(
  projects: Project[],
  filter: ProjectFilterValue,
): Project[] {
  if (filter === "ALL") {
    return projects;
  }
  return projects.filter((project) => project.jurisdiction_code === filter);
}

/** Case-insensitive substring search over the two fields a reader would
 * recognise a project by: its title and its id. */
export function searchProjects(projects: Project[], query: string): Project[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) {
    return projects;
  }
  return projects.filter((project) =>
    [project.title, project.project_id].some((field) =>
      field.toLowerCase().includes(needle),
    ),
  );
}

/** Newest first. The list has no declared order, and creation time is the
 * only ordering the rows carry. An unparseable stamp sorts last rather than
 * scrambling the rows around it. */
export function newestFirst(projects: Project[]): Project[] {
  return [...projects].sort(
    (left, right) =>
      (parsedTime(right.created_at) ?? -Infinity) -
      (parsedTime(left.created_at) ?? -Infinity),
  );
}
