import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const backend = process.env.LUNARSIGHT_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 750,
    rollupOptions: {
      output: {
        manualChunks: { "three-core": ["three"] },
      },
    },
  },
  preview: { host: "127.0.0.1", proxy: { "/api": backend } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": backend,
    },
  },
});
