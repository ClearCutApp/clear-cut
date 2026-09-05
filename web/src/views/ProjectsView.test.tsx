import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import type { Project } from "../api/client";
import { stubFetch, type StubRoute } from "../testing/fetchStub";
import { ProjectsView } from "./ProjectsView";

const VERANO: Project = {
  project_id: "prj-1",
  title: "El Ultimo Verano",
  jurisdiction_code: "AR",
  created_at: "2026-09-04T12:00:00Z",
};

const ECHOES: Project = {
  project_id: "prj-2",
  title: "Night Echoes",
  jurisdiction_code: "MX",
  created_at: "2026-09-03T12:00:00Z",
};

const JURISDICTIONS = [
  { code: "AR", display_name: "Argentina" },
  { code: "MX", display_name: "Mexico" },
];

function ok(body: unknown) {
  return { status: 200, body };
}

/** Renders the router's current path so a test can assert a navigation. */
function LocationProbe() {
  return <span hidden data-testid="location">{useLocation().pathname}</span>;
}

function renderView(routes: Parameters<typeof stubFetch>[0]) {
  const stub = stubFetch(routes);
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<ProjectsView />} />
        <Route path="/projects/:projectId" element={<p>project view</p>} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>,
  );
  return stub;
}

function loaded(extra: Record<string, StubRoute> = {}) {
  return renderView({
    projects: ok([VERANO, ECHOES]),
    jurisdictions: ok(JURISDICTIONS),
    ...extra,
  });
}

describe("ProjectsView", () => {
  it("lists the projects the server holds, newest first", async () => {
    loaded();

    expect(await screen.findByRole("heading", { name: "El Ultimo Verano" })).toBeInTheDocument();
    const titles = screen.getAllByRole("heading", { level: 3 }).map((one) => one.textContent);
    expect(titles).toEqual(["El Ultimo Verano", "Night Echoes"]);
  });

  it("shows the numbers the list adds up to", async () => {
    loaded();

    await screen.findByText("Jurisdictions");
    expect(screen.getByText("Jurisdictions").previousSibling).toHaveTextContent("2");
    expect(screen.getByText("On this server").previousSibling?.previousSibling).toHaveTextContent(
      "2",
    );
  });

  it("narrows the rows by jurisdiction and by search", async () => {
    loaded();
    await screen.findByRole("heading", { name: "El Ultimo Verano" });

    fireEvent.click(screen.getByRole("tab", { name: "Mexico 1" }));
    expect(screen.queryByRole("heading", { name: "El Ultimo Verano" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Night Echoes" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "All projects 2" }));
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "verano" } });
    expect(screen.queryByRole("heading", { name: "Night Echoes" })).toBeNull();
  });

  it("says so when a filter matches nothing, without emptying the tabs", async () => {
    loaded();
    await screen.findByRole("heading", { name: "El Ultimo Verano" });

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "nothing" } });

    expect(screen.getByText("No project matches the current filter.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "All projects 2" })).toBeInTheDocument();
  });

  it("tells an empty server apart from a failed read", async () => {
    renderView({ projects: ok([]), jurisdictions: ok(JURISDICTIONS) });

    expect(await screen.findByText("This server holds no projects yet.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows the server's sentence when the list fails, and no rows", async () => {
    renderView({
      projects: { status: 500, body: "internal error" },
      jurisdictions: ok(JURISDICTIONS),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("internal error");
    expect(screen.queryByRole("heading", { level: 3 })).toBeNull();
  });

  it("creates a project and opens it", async () => {
    const created: Project = {
      project_id: "prj-9",
      title: "Condor Rising",
      jurisdiction_code: "AR",
      created_at: "2026-09-05T12:00:00Z",
    };
    const { calls } = loaded({ "create-project": ok(created) });
    await screen.findByRole("heading", { name: "El Ultimo Verano" });

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Condor Rising" } });
    fireEvent.change(screen.getByLabelText("Jurisdiction"), { target: { value: "AR" } });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/projects/prj-9"));
    expect(calls.find((call) => call.kind === "create-project")?.body).toEqual({
      title: "Condor Rising",
      jurisdiction_code: "AR",
    });
  });

  it("keeps the reader on the list and shows the refusal when creation fails", async () => {
    loaded({ "create-project": { status: 400, body: "title is required" } });
    await screen.findByRole("heading", { name: "El Ultimo Verano" });

    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "x" } });
    fireEvent.change(screen.getByLabelText("Jurisdiction"), { target: { value: "AR" } });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("title is required");
    expect(screen.getByTestId("location")).toHaveTextContent("/");
  });

  it("draws no poster, no team and no clearance totals it cannot source", async () => {
    loaded();
    await screen.findByRole("heading", { name: "El Ultimo Verano" });

    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByText("Clearance totals")).toBeInTheDocument();
    expect(screen.getByText(/No endpoint sums them across projects/)).toBeInTheDocument();
  });
});
