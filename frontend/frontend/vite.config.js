import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    proxy: {
      // Proxy all backend routes to FastAPI at port 8000
      '/analyze': 'http://localhost:8000',
      '/login': 'http://localhost:8000',
      '/signup': 'http://localhost:8000',
      '/settings': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
      '/reports': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
