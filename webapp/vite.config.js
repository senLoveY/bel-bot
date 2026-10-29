import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      // две страницы: Mini App (index.html) и сайт админки (admin/index.html → /admin)
      input: {
        main: new URL("./index.html", import.meta.url).pathname,
        admin: new URL("./admin/index.html", import.meta.url).pathname,
      },
    },
  },
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
  },
});
