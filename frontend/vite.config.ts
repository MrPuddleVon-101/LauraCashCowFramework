import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// A GitHub Pages build is served from a repository subpath, so the asset URLs
// have to carry it. Everything else (local dev, the Docker image) stays at root.
export default defineConfig({
  base: process.env.PAGES_BASE ?? "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8077", changeOrigin: true } },
  },
});
