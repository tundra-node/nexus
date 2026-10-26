import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 80,
    proxy: {
      // Defaults to the docker-compose service name. Override for native runs:
      //   VITE_API_PROXY=http://127.0.0.1:8000 pnpm dev
      '/api': process.env.VITE_API_PROXY || 'http://nginx'
    }
  }
})
