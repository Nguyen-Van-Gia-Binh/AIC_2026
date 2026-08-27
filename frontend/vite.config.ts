import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api/* sang backend FastAPI (127.0.0.1:8000) — trinh duyet chi thay 1 origin luc dev,
// khong can dua vao CORS lam co che chinh (van bat CORS o backend lam du phong — xem main.py).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
