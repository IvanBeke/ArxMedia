import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  base: '/static/web/',
  build: {
    outDir: '../static/web',
    emptyOutDir: true,
    manifest: true,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    host: '0.0.0.0',       // necesario para que Docker exponga el puerto
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/api': {
        target: 'http://app:8000',   // nombre del servicio en compose, no localhost
        changeOrigin: true
      },
      '/oauth': {
        target: 'http://app:8000',
        changeOrigin: true
      }
    }
  }
})
