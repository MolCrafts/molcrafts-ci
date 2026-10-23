import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { UrlStateProvider } from "./lib/use-url-state";
import "./plugins/builtins";
import "@molcrafts/ui/styles.css";
import "./styles/tailwind.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("missing #root");
}

createRoot(root).render(
  <StrictMode>
    <UrlStateProvider>
      <App />
    </UrlStateProvider>
  </StrictMode>,
);
