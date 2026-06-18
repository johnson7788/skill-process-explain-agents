import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3686,
    proxy: {
      "/api": {
        target: "http://localhost:8686",
        changeOrigin: true,
      },
      "/chat": {
        target: "http://localhost:8686",
        changeOrigin: true,
      },
    },
  },
});
