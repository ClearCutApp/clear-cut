import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import { getHealth, type ServerMode } from "../api/client";

const ServerModeContext = createContext<ServerMode | null>(null);

export interface ServerModeProviderProps {
  children: ReactNode;
}

/**
 * Asks the health endpoint once for the whole app, so the demo banner can
 * render on every route including the landing page. The mode cannot change
 * under a running server, and a failed check leaves `mode` null: an
 * unreachable health endpoint is not evidence about the data, so claiming
 * it is planted would be its own kind of lie.
 */
export function ServerModeProvider({
  children,
}: ServerModeProviderProps): ReactElement {
  const [mode, setMode] = useState<ServerMode | null>(null);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((health) => {
        if (!cancelled) {
          setMode(health.mode);
        }
      })
      .catch(() => {
        // Deliberately silent, see above.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ServerModeContext.Provider value={mode}>{children}</ServerModeContext.Provider>
  );
}

/** `null` until the health endpoint answers, and forever if it never does. */
export function useServerMode(): ServerMode | null {
  return useContext(ServerModeContext);
}
