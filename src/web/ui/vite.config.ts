import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  base: '/static/web/',
  build: {
    outDir: '../static/web',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: fileURLToPath(new URL('./src/main.ts', import.meta.url)),
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    pool: 'forks',
    isolate: true,
    deps: { optimizer: { web: { include: ['vue', 'vue-router', 'pinia'] } } },
    watch: false,
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    watch: process.env.VITEST ? { usePolling: false } : { usePolling: true, interval: 300 },
    proxy: {
      '/api': {
        target: 'http://app:8000',
        changeOrigin: true,
      },
      '/oauth': {
        target: 'http://app:8000',
        changeOrigin: true,
      },
    },
  },
})
