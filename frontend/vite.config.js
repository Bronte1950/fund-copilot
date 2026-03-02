import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to FastAPI during development
      '/health': 'http://localhost:8010',
      '/retrieve': 'http://localhost:8010',
      '/chat': 'http://localhost:8010',
      '/docs': 'http://localhost:8010',
      '/admin': 'http://localhost:8010',
    },
  },
})
