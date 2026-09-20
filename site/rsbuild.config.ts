import path from "node:path";
import { defineConfig } from "@rsbuild/core";
import { pluginReact } from "@rsbuild/plugin-react";
import { pluginTailwindcss } from "@rsbuild/plugin-tailwindcss";
import { pluginMockServer } from "rspack-plugin-mock/rsbuild";

const root = import.meta.dirname;
const assetPrefix = (process.env.PUBLIC_BASE ?? "auto").trim() || "auto";
const useMock = process.env.PUBLIC_USE_MOCK !== "0";
// Where the browser reads published data from. A relative default keeps the dev
// mock and `dev:data` working; production points at the `data` branch, and then
// there is nothing local to copy into the bundle.
const dataBase = (process.env.PUBLIC_DATA_BASE ?? "./data").trim() || "./data";
const bundlesData = dataBase.startsWith(".") || dataBase.startsWith("/");

export default defineConfig({
  root,
  plugins: [
    pluginTailwindcss(),
    pluginReact(),
    // Dev-server mock for /data/* (rspack-plugin-mock). Set PUBLIC_USE_MOCK=0
    // to serve real files from public/data instead.
    ...(useMock
      ? [
          pluginMockServer({
            cwd: root,
            dir: "mock",
            prefix: "/data",
          }),
        ]
      : []),
  ],
  resolve: {
    alias: {
      "@": path.resolve(root, "src"),
    },
  },
  source: {
    entry: {
      index: "./src/index.tsx",
    },
    define: {
      "process.env.PUBLIC_DATA_BASE": JSON.stringify(dataBase),
    },
  },
  html: {
    title: "MolCrafts CI",
    template: "./src/index.html",
  },
  output: {
    distPath: {
      root: path.resolve(root, "dist"),
    },
    assetPrefix,
    copy: bundlesData
      ? [
          {
            from: path.resolve(root, "public/data"),
            to: "data",
          },
        ]
      : [],
  },
  server: {
    port: 4174,
    // Bind IPv4 — default ::1 rejects curl/browsers on 127.0.0.1.
    host: "127.0.0.1",
  },
});
