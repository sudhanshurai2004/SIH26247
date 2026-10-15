import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser uses relative /api URLs. Vite alone talks to the local API while
// developing, so a desktop client never needs a localhost URL in its code.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  preview: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: true
  }
});
