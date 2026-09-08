import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthView, authErrorCode, safeDestination } from "./AuthView";

/** A Firebase failure is an object carrying a `code`, which is the only part
 *  of it this view reads. */
function failure(code: string): Error & { code: string } {
  return Object.assign(new Error(code), { code });
}

const boundary = vi.hoisted(() => ({
  configured: true,
  popup: vi.fn(),
  redirect: vi.fn(),
  redirectResult: vi.fn(),
}));

vi.mock("../auth/firebase", () => ({
  firebaseAuth: () => (boundary.configured ? {} : null),
  loadFirebaseAuth: async () => null,
}));
vi.mock("firebase/auth", async (original) => ({
  ...(await original<typeof import("firebase/auth")>()),
  signInWithPopup: (...args: unknown[]) => boundary.popup(...args),
  signInWithRedirect: (...args: unknown[]) => boundary.redirect(...args),
  getRedirectResult: (...args: unknown[]) => boundary.redirectResult(...args),
}));
vi.mock("../state/AuthContext", () => ({
  useAuth: () => ({ user: null, ready: true, configured: boundary.configured, error: null }),
}));

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<AuthView />} />
        <Route path="/projects" element={<h1>Projects</h1>} />
        <Route path="/verify-email" element={<h1>Verify email</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

const verified = { user: { emailVerified: true } };

beforeEach(() => {
  boundary.configured = true;
  boundary.popup.mockReset();
  boundary.redirect.mockReset().mockResolvedValue(undefined);
  boundary.redirectResult.mockReset().mockResolvedValue(null);
});

describe("continuing with Google", () => {
  it("carries Google's mark, which its branding requires of the button", () => {
    const { container } = renderLogin();
    const button = screen.getByRole("button", { name: "Continue with Google" });
    expect(button.querySelector("svg.google-mark")).not.toBeNull();
    expect(container.querySelector("svg.google-mark")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("signs a verified identity in and leaves for the destination", async () => {
    boundary.popup.mockResolvedValue(verified);
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Projects" })).toBeVisible());
  });

  it("says nothing when the chooser is closed, because cancelling is not failing", async () => {
    boundary.popup.mockRejectedValue(failure("auth/popup-closed-by-user"));
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Continue with Google" })).toBeEnabled());
    expect(screen.queryByRole("status")).toBeNull();
    expect(boundary.redirect).not.toHaveBeenCalled();
  });

  it("asks again by redirect when the environment refused the popup", async () => {
    boundary.popup.mockRejectedValue(failure("auth/popup-blocked"));
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    await waitFor(() => expect(boundary.redirect).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("names an unauthorised domain instead of blaming the reader's details", async () => {
    boundary.popup.mockRejectedValue(failure("auth/unauthorized-domain"));
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/authorised sign-in domain/);
  });

  it("reports an unrecognised failure rather than swallowing it", async () => {
    boundary.popup.mockRejectedValue(failure("auth/network-request-failed"));
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/could not complete that request/);
  });

  it("collects the credential the redirect carries back", async () => {
    boundary.redirectResult.mockResolvedValue(verified);
    renderLogin();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Projects" })).toBeVisible());
  });

  it("refuses, and says why, when account access is unconfigured", () => {
    boundary.configured = false;
    renderLogin();
    const button = screen.getByRole("button", { name: "Continue with Google" });
    expect(button).toBeDisabled();
    expect(button.getAttribute("aria-describedby")).toBe("auth-unconfigured");
    expect(screen.getByRole("alert")).toHaveTextContent(/awaiting configuration/);
  });
});

describe("reading a Firebase failure", () => {
  it("reads the code a Firebase error carries", () => {
    expect(authErrorCode(failure("auth/popup-blocked"))).toBe("auth/popup-blocked");
  });
  it("reads nothing from a value that carries no code", () => {
    expect(authErrorCode(new Error("boom"))).toBe("");
    expect(authErrorCode(null)).toBe("");
    expect(authErrorCode({ code: 7 })).toBe("");
  });
});

describe("the destination a sign-in returns to", () => {
  it("keeps a private destination", () => {
    expect(safeDestination("/projects/demo-project")).toBe("/projects/demo-project");
  });
  it("refuses a destination that leaves the app", () => {
    expect(safeDestination("https://elsewhere.example/projects")).toBe("/projects");
    expect(safeDestination("/projects\\evil")).toBe("/projects");
  });
});
