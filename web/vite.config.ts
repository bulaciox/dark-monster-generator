import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Tailwind 4 runs as a Vite plugin: no tailwind.config.js, no PostCSS.
// Theming lives in src/index.css via @theme.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // The FastAPI backend; keeps the browser on a single origin.
    proxy: { '/api': 'http://localhost:8000' },
  },
})
