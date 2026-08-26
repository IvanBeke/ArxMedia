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
    rollupOptions: {
      input: fileURLToPath(new URL('./src/main.js', import.meta.url)),
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.js'],
    pool: 'forks',
    poolOptions: { forks: { singleFork: true } },
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
