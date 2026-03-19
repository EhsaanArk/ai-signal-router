import { defineConfig } from "vite";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { writeFileSync, mkdirSync } from "fs";

/** Generates version.json in dist/ and injects __BUILD_TIME__ global */
function versionPlugin(): Plugin {
  const buildTime = Date.now();
  return {
    name: "version-json",
    config() {
      return { define: { "window.__BUILD_TIME__": JSON.stringify(buildTime) } };
    },
    closeBundle() {
      const dir = path.resolve(__dirname, "dist");
      mkdirSync(dir, { recursive: true });
      writeFileSync(
        path.resolve(dir, "version.json"),
        JSON.stringify({ buildTime }),
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), versionPlugin()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react-dom") || id.includes("node_modules/react/") || id.includes("node_modules/react-router")) {
            return "vendor";
          }
          if (id.includes("node_modules/@tanstack/react-query")) {
            return "query";
          }
          if (id.includes("node_modules/@radix-ui")) {
            return "ui";
          }
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: process.env.API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
