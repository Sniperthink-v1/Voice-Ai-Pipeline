import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5174, // Different port from old frontend
    host: true,
    allowedHosts: [
      'localhost',
      '127.0.0.1',
      '.ngrok-free.app', // Allow all ngrok hosts
      '.ngrok.io',       // Allow older ngrok domains
    ],
  },
})
