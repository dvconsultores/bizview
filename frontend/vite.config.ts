import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Mirrors deploy/caddy/Caddyfile so e2e exercises the same headers.
const sharedPageHeaders: Plugin = {
  name: "shared-page-headers",
  configurePreviewServer(server) {
    server.middlewares.use((req, res, next) => {
      if (req.url?.startsWith("/s/")) {
        res.setHeader("X-Robots-Tag", "noindex, nofollow");
        res.setHeader("Cache-Control", "no-store");

        const originalSetHeader = res.setHeader.bind(res);
        res.setHeader = ((name: string, value: string | string[]) => {
          if (name.toLowerCase() === "cache-control") {
            return res;
          }
          return originalSetHeader(name, value);
        }) as typeof res.setHeader;
      }

      next();
    });
  },
};

// Browser support (research R8): iOS/Safari 14+, Chrome 87+, Firefox 78+, Edge 88+.
export default defineConfig({
  plugins: [react(), sharedPageHeaders],
  build: {
    target: ["es2020", "safari14", "chrome87", "firefox78", "edge88"],
    cssTarget: ["safari14", "chrome87", "firefox78", "edge88"],
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.API_TARGET ?? "http://localhost:8000" } },
  },
  test: { environment: "jsdom", include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx"] },
});
