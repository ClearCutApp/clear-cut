import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "firebase/auth";
import { AuthProvider } from "../state/AuthContext";
import { RequireIdentity } from "./RequireIdentity";
import { safeDestination } from "../views/AuthView";

const boundary = vi.hoisted(() => ({ observe: (_: User | null) => {}, configured: true }));
vi.mock("./firebase", () => ({ firebaseAuth: () => boundary.configured ? {} : null, loadFirebaseAuth: async () => null }));
vi.mock("firebase/auth", async (original) => ({
  ...await original<typeof import("firebase/auth")>(),
  onIdTokenChanged: (_auth: unknown, callback: (user: User | null) => void) => {
    boundary.observe = callback; return () => {};
  },
}));
function renderGate() {
  return render(<MemoryRouter initialEntries={["/projects/private"]}><AuthProvider><Routes>
    <Route element={<RequireIdentity />}><Route path="/projects/private" element={<h1>Private project</h1>} /></Route>
    <Route path="/login" element={<h1>Sign in</h1>} />
    <Route path="/verify-email" element={<h1>Verify email</h1>} />
  </Routes></AuthProvider></MemoryRouter>);
}
beforeEach(() => { boundary.configured = true; });
describe("private workspace identity", () => {
  it("does not mount private data before identity resolves", () => {
    renderGate(); expect(screen.queryByText("Private project")).toBeNull();
  });
  it("routes a signed-out identity to login", async () => {
    renderGate(); act(() => boundary.observe(null));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
  it("requires verified email", async () => {
    renderGate(); act(() => boundary.observe({ uid: "user", emailVerified: false } as User));
    expect(await screen.findByRole("heading", { name: "Verify email" })).toBeInTheDocument();
  });
  it("opens the project only after verified identity", async () => {
    renderGate(); act(() => boundary.observe({ uid: "user", emailVerified: true } as User));
    expect(await screen.findByRole("heading", { name: "Private project" })).toBeInTheDocument();
  });
  it("missing configuration stays closed", async () => {
    boundary.configured = false; renderGate();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("configuration"));
    expect(screen.queryByText("Private project")).toBeNull();
  });
  it("never restores an external destination", () => {
    expect(safeDestination("https://attacker.example")).toBe("/projects");
    expect(safeDestination("//attacker.example")).toBe("/projects");
    expect(safeDestination("/projects/one/script")).toBe("/projects/one/script");
  });
});
