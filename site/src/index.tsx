import { StrictMode } from "react";
import { createRoot } from "react-dom/client";


import { App } from "./App";
import "./plugins/builtins";
import "@molcrafts/design/styles.css";
import "./styles/tailwind.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("missing #root");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
