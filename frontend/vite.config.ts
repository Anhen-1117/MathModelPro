import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    proxy: {
      '/api/v1/ws': {
        target: 'ws://127.0.0.1:8001',
        ws: true,
        changeOrigin: true
      },
      '/api/v2/ws': {
        target: 'ws://127.0.0.1:8001',
        ws: true,
        changeOrigin: true
      },
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://127.0.0.1:8001',
        ws: true
      }
    }
  }
})
