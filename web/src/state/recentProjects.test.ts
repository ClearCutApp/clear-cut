import { describe, expect, it } from "vitest";

import {
  RECENT_PROJECTS_KEY,
  RECENT_PROJECTS_LIMIT,
  jurisdictionFor,
  readRecentProjects,
  rememberProject,
} from "./recentProjects";

describe("readRecentProjects", () => {
  it("reads an empty browser as an empty list", () => {
    expect(readRecentProjects()).toEqual([]);
  });

  it("reads malformed storage as an empty list rather than throwing", () => {
    localStorage.setItem(RECENT_PROJECTS_KEY, "{not json");

    expect(readRecentProjects()).toEqual([]);
  });

  it("reads a non-array as an empty list", () => {
    localStorage.setItem(RECENT_PROJECTS_KEY, JSON.stringify({ projectId: "x" }));

    expect(readRecentProjects()).toEqual([]);
  });

  it("drops entries that lack one of the three string fields", () => {
    localStorage.setItem(
      RECENT_PROJECTS_KEY,
      JSON.stringify([
        { projectId: "kept", jurisdictionCode: "US", openedAt: "2026-09-01T00:00:00.000Z" },
        { projectId: "no-code", openedAt: "2026-09-01T00:00:00.000Z" },
        "not an object",
      ]),
    );

    expect(readRecentProjects().map((project) => project.projectId)).toEqual([
      "kept",
    ]);
  });
});

describe("rememberProject", () => {
  it("puts the newest project first with the moment it was opened", () => {
    rememberProject("older", "US", new Date("2026-09-01T00:00:00Z"));
    rememberProject("newer", "ES", new Date("2026-09-02T00:00:00Z"));

    expect(readRecentProjects()).toEqual([
      { projectId: "newer", jurisdictionCode: "ES", openedAt: "2026-09-02T00:00:00.000Z" },
      { projectId: "older", jurisdictionCode: "US", openedAt: "2026-09-01T00:00:00.000Z" },
    ]);
  });

  it("keeps one entry per project, moving a reopened project to the front", () => {
    rememberProject("a", "US");
    rememberProject("b", "US");
    rememberProject("a", "ES");

    expect(readRecentProjects().map((project) => project.projectId)).toEqual([
      "a",
      "b",
    ]);
    expect(readRecentProjects()[0].jurisdictionCode).toBe("ES");
  });

  it("caps the list at the limit, dropping the oldest", () => {
    for (let index = 0; index <= RECENT_PROJECTS_LIMIT; index += 1) {
      rememberProject(`project-${index}`, "US");
    }

    const ids = readRecentProjects().map((project) => project.projectId);
    expect(ids).toHaveLength(RECENT_PROJECTS_LIMIT);
    expect(ids[0]).toBe(`project-${RECENT_PROJECTS_LIMIT}`);
    expect(ids).not.toContain("project-0");
  });
});

describe("jurisdictionFor", () => {
  it("answers the remembered code for a known project and null otherwise", () => {
    rememberProject("known", "MX");

    expect(jurisdictionFor("known")).toBe("MX");
    expect(jurisdictionFor("unknown")).toBeNull();
  });
});
