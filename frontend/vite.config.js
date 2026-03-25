import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../frontend_dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    host: true,
    strictPort: true,
    hmr: {
      host: "localhost",
      port: 5173,
    },
    watch: {
      usePolling: true,
    },
    proxy: {
      "/api": "http://web:8000",
      "/media": "http://web:8000",
      "/downloads": "http://web:8000",
      "/events/[^/]+/qr": "http://web:8000",
      "/django-admin": "http://web:8000"
    }
  }
});
