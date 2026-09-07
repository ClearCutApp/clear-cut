import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { AuthProvider } from "./state/AuthContext";
import { LocaleProvider } from "./state/LocaleContext";
import { App } from "./App";
import { ServerModeProvider } from "./state/ServerModeContext";
import "./index.css";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("root element not found");
}

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <ServerModeProvider>
        <LocaleProvider><AuthProvider><App /></AuthProvider></LocaleProvider>
      </ServerModeProvider>
    </BrowserRouter>
  </StrictMode>,
);
