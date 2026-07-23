import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Accept requests forwarded through an ngrok tunnel (any host). Needed so a
    // friend can open the public ngrok URL; Vite otherwise blocks unknown hosts.
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/socket.io": { target: "http://localhost:8000", ws: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // Split heavy vendor libraries into separate chunks so no single
        // bundle balloons past the warning limit. Function form avoids the
        // circular-chunk issue: react stays in `vendor`, and libraries that
        // depend on it (mui, charts) only import one-way from vendor.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          // Only split the big leaf libraries that import react one-way; keep
          // react/router/axios/socket.io together in `vendor` to avoid cycles.
          if (id.includes("recharts") || id.includes("d3-")) return "charts";
          if (id.includes("@mui") || id.includes("@emotion")) return "mui";
          return "vendor";
        },
      },
    },
  },
});
