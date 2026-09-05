import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { stubFetch } from "../testing/fetchStub";
import { useProjectList } from "./useProjectList";

const PROJECT = {
  project_id: "prj-1",
  title: "El Ultimo Verano",
  jurisdiction_code: "AR",
  created_at: "2026-09-04T12:00:00Z",
};

const CREATED = {
  project_id: "prj-2",
  title: "Night Echoes",
  jurisdiction_code: "MX",
  created_at: "2026-09-05T12:00:00Z",
};

const JURISDICTIONS = [
  { code: "AR", display_name: "Argentina" },
  { code: "MX", display_name: "Mexico" },
];

function ok(body: unknown) {
  return { status: 200, body };
}

describe("useProjectList", () => {
  it("starts empty-handed and fills the list and the jurisdictions from their GETs", async () => {
    stubFetch({ projects: ok([PROJECT]), jurisdictions: ok(JURISDICTIONS) });

    const { result } = renderHook(useProjectList);

    expect(result.current.projects).toBeNull();
    await waitFor(() => expect(result.current.projects).toEqual([PROJECT]));
    expect(result.current.jurisdictions).toEqual(JURISDICTIONS);
    expect(result.current.projectsError).toBeNull();
  });

  it("tells an empty server apart from a failed read", async () => {
    stubFetch({ projects: ok([]), jurisdictions: ok(JURISDICTIONS) });

    const { result } = renderHook(useProjectList);

    await waitFor(() => expect(result.current.projects).toEqual([]));
    expect(result.current.projectsError).toBeNull();
  });

  it("exposes the server's sentence when the list fails", async () => {
    stubFetch({ projects: { status: 500, body: "internal error" }, jurisdictions: ok([]) });

    const { result } = renderHook(useProjectList);

    await waitFor(() => expect(result.current.projectsError).toBe("internal error"));
    expect(result.current.projects).toBeNull();
  });

  it("keeps the projects when only the jurisdictions fail", async () => {
    stubFetch({
      projects: ok([PROJECT]),
      jurisdictions: { status: 500, body: "corpus unavailable" },
    });

    const { result } = renderHook(useProjectList);

    await waitFor(() => expect(result.current.jurisdictionsError).toBe("corpus unavailable"));
    expect(result.current.projects).toEqual([PROJECT]);
    expect(result.current.jurisdictions).toBeNull();
  });

  it("puts the created project at the head of the list, as the server stored it", async () => {
    const { calls } = stubFetch({
      projects: ok([PROJECT]),
      jurisdictions: ok(JURISDICTIONS),
      "create-project": ok(CREATED),
    });
    const { result } = renderHook(useProjectList);
    await waitFor(() => expect(result.current.projects).toHaveLength(1));

    let outcome;
    await act(async () => {
      outcome = await result.current.create({ title: "Night Echoes", jurisdiction_code: "MX" });
    });

    expect(outcome).toEqual({ ok: true, value: CREATED });
    expect(result.current.projects).toEqual([CREATED, PROJECT]);
    expect(calls.find((call) => call.kind === "create-project")?.body).toEqual({
      title: "Night Echoes",
      jurisdiction_code: "MX",
    });
  });

  it("returns the refusal as a message and leaves the list untouched", async () => {
    stubFetch({
      projects: ok([PROJECT]),
      jurisdictions: ok(JURISDICTIONS),
      "create-project": { status: 400, body: "title is required" },
    });
    const { result } = renderHook(useProjectList);
    await waitFor(() => expect(result.current.projects).toHaveLength(1));

    let outcome;
    await act(async () => {
      outcome = await result.current.create({ title: "", jurisdiction_code: "MX" });
    });

    expect(outcome).toEqual({ ok: false, message: "title is required" });
    expect(result.current.projects).toEqual([PROJECT]);
    expect(result.current.creating).toBe(false);
  });
});
