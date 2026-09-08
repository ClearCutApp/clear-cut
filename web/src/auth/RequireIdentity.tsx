import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "../state/AuthContext";
import { useServerMode } from "../state/ServerModeContext";

export function RequireIdentity() {
  const identity = useAuth();
  const mode = useServerMode();
  const location = useLocation();
  if (mode === "mock") return <Outlet />;
  if (!identity.ready) return <main className="auth-page">
      <p>Checking account access…</p>
      </main>;
  if (identity.error) return <main className="auth-page">
      <p role="alert">{identity.error}</p>
      <a href="/">ClearCut</a>
      </main>;
  if (!identity.user) return <Navigate to="/login" state={{ from: location.pathname + location.hash }} replace />;
  if (!identity.user.emailVerified) return <Navigate to="/verify-email" state={{ from: location.pathname + location.hash }} replace />;
  return <div key={identity.user.uid}>
      <Outlet />
      </div>;
}
