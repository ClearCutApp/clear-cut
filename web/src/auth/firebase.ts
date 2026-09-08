import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import { getClientConfig } from "../api/client";

let configured: Auth | null | undefined;
export function firebaseAuth(): Auth | null {
  if (configured !== undefined) return configured;
  const apiKey = import.meta.env.VITE_FIREBASE_API_KEY as string | undefined;
  const authDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined;
  const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined;
  const appId = import.meta.env.VITE_FIREBASE_APP_ID as string | undefined;
  configured = apiKey && authDomain && projectId && appId
    ? getAuth(getApps().length ? getApp() : initializeApp({ apiKey, authDomain, projectId, appId })) : null;
  return configured;
}

export async function loadFirebaseAuth(): Promise<Auth | null> {
  if (firebaseAuth()) return configured ?? null;
  const config = await getClientConfig();
  if (!config.apiKey || !config.authDomain || !config.projectId || !config.appId) return null;
  configured = getAuth(getApps().length ? getApp() : initializeApp(config));
  return configured;
}
