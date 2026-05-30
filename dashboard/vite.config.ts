import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard talks to the collector API. In dev we proxy /api, /v1 and
// /metrics to the server so there are no CORS surprises; in production the
// dashboard is served behind the same origin (or VITE_API_BASE is set).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/v1": "http://localhost:8000",
      "/metrics": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
