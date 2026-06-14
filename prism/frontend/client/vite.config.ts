import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  base: '/dashboard/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@shared": path.resolve(__dirname, "../shared"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      // In Docker dev: set VITE_PROXY_TARGET=http://nginx
      // Local dev: http://localhost:8000 (old flat backend, deprecated)
      "/api": process.env.VITE_PROXY_TARGET || "http://localhost:8000",
    },
  },
});
