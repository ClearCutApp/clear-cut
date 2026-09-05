import { describe, expect, it } from "vitest";

import type { Project } from "../../api/client";
import {
  applyProjectFilter,
  newestFirst,
  projectMetrics,
  projectTabs,
  searchProjects,
} from "./model";

const NOW = new Date("2026-09-05T12:00:00Z");

function project(overrides: Partial<Project> = {}): Project {
  return {
    project_id: "prj-1",
    title: "El Ultimo Verano",
    jurisdiction_code: "AR",
    created_at: "2026-09-04T12:00:00Z",
    ...overrides,
  };
}

const PROJECTS = [
  project(),
  project({ project_id: "prj-2", title: "Night Echoes", jurisdiction_code: "MX" }),
  project({
    project_id: "prj-3",
    title: "Under the Ice",
    jurisdiction_code: "AR",
    created_at: "2026-06-01T12:00:00Z",
  }),
];

describe("projectMetrics", () => {
  it("counts the projects, the jurisdictions among them and the week's arrivals", () => {
    expect(projectMetrics(PROJECTS, NOW)).toEqual({
      total: 3,
      jurisdictions: 2,
      addedThisWeek: 2,
    });
  });

  it("is all zeroes for an empty list rather than a placeholder", () => {
    expect(projectMetrics([], NOW)).toEqual({
      total: 0,
      jurisdictions: 0,
      addedThisWeek: 0,
    });
  });

  it("counts a project with an unreadable stamp, but in no week", () => {
    const metrics = projectMetrics([project({ created_at: "not a date" })], NOW);

    expect(metrics.total).toBe(1);
    expect(metrics.addedThisWeek).toBe(0);
  });
});

describe("projectTabs", () => {
  it("offers All and one tab per jurisdiction present, each with its own count", () => {
    expect(projectTabs(PROJECTS)).toEqual([
      { value: "ALL", code: null, count: 3 },
      { value: "AR", code: "AR", count: 2 },
      { value: "MX", code: "MX", count: 1 },
    ]);
  });

  it("offers All alone when there are no projects", () => {
    expect(projectTabs([])).toEqual([{ value: "ALL", code: null, count: 0 }]);
  });
});

describe("applyProjectFilter", () => {
  it("passes everything through for All", () => {
    expect(applyProjectFilter(PROJECTS, "ALL")).toEqual(PROJECTS);
  });

  it("narrows to one jurisdiction", () => {
    expect(applyProjectFilter(PROJECTS, "MX").map((one) => one.project_id)).toEqual([
      "prj-2",
    ]);
  });
});

describe("searchProjects", () => {
  it("returns every project for a blank query", () => {
    expect(searchProjects(PROJECTS, "   ")).toEqual(PROJECTS);
  });

  it("matches a title regardless of case", () => {
    expect(searchProjects(PROJECTS, "night").map((one) => one.title)).toEqual([
      "Night Echoes",
    ]);
  });

  it("matches an id, which is how a deep link names a project", () => {
    expect(searchProjects(PROJECTS, "prj-3").map((one) => one.project_id)).toEqual([
      "prj-3",
    ]);
  });
});

describe("newestFirst", () => {
  it("orders by creation time, newest first, without mutating its input", () => {
    const input = [...PROJECTS];

    expect(newestFirst(input).map((one) => one.project_id)).toEqual([
      "prj-1",
      "prj-2",
      "prj-3",
    ]);
    expect(input).toEqual(PROJECTS);
  });

  it("puts a project with an unreadable stamp last rather than scrambling the rest", () => {
    const broken = project({ project_id: "prj-x", created_at: "not a date" });

    expect(newestFirst([broken, ...PROJECTS]).map((one) => one.project_id)).toEqual([
      "prj-1",
      "prj-2",
      "prj-3",
      "prj-x",
    ]);
  });
});
