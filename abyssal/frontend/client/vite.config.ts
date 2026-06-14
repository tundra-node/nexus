import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 80,
    proxy: {
      '/api': 'http://nginx'
    }
  }
})
