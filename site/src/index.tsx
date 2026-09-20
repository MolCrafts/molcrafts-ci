import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

/*
 * The constitution's families (visual-language.md section 1), self-hosted.
 * Bundled rather than fetched: this site is published to GitHub Pages and
 * should not depend on a third party being reachable to render its own type.
 * Only the weights the constitution uses — 400 body, 500 emphasis, 600 titles
 * — and only the latin subset: the whole set is 440 kB of cyrillic and greek
 * this interface never renders.
 */
import "@fontsource/geist-sans/latin-400.css";
import "@fontsource/geist-sans/latin-500.css";
import "@fontsource/geist-sans/latin-600.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-500.css";

import { App } from "./App";
import "./plugins/builtins";
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
