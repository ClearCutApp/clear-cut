import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { onIdTokenChanged, signOut, type User } from "firebase/auth";
import { setIdentityTokenProvider } from "../api/client";
import { RECENT_PROJECTS_KEY } from "./recentProjects";
import { firebaseAuth, loadFirebaseAuth } from "../auth/firebase";

interface State { user: User | null; ready: boolean; configured: boolean; error: string | null; }
const Context = createContext<State>({ user: null, ready: false, configured: false, error: null });
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ user: null, ready: false, configured: false, error: null });
  useEffect(() => {
    let active = true;
    let unsubscribe = () => {};
    let previousUser: string | null | undefined;
    async function connect() {
      try {
        const auth = firebaseAuth() ?? await loadFirebaseAuth();
        if (!active) return;
        if (!auth) throw new Error("Missing account configuration");
        unsubscribe = onIdTokenChanged(auth, (user) => {
          if (!active) return;
          if (previousUser !== user?.uid) {
            try { localStorage.removeItem(RECENT_PROJECTS_KEY); } catch { /* Storage is optional. */ }
            previousUser = user?.uid;
          }
          setIdentityTokenProvider(async () => user ? user.getIdToken() : null);
          setState({ user, ready: true, configured: true, error: null });
        }, () => {
          setIdentityTokenProvider(async () => null);
          setState({ user: null, ready: true, configured: true, error: "Account access is unavailable. Try again." });
        });
      } catch {
        if (active) setState({ user: null, ready: true, configured: false, error: "Account access is awaiting configuration." });
      }
    }
    void connect();
    return () => { active = false; unsubscribe();
      setIdentityTokenProvider(async () => null); };
  }, []);
  return <Context.Provider value={state}>{children}</Context.Provider>;
}
export function useAuth() { return useContext(Context); }
export async function logOut() {
  const auth = firebaseAuth();
  if (auth) await signOut(auth);
}
