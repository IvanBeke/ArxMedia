import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      // The worker is emitted into /static/web/ but served at /sw.js for root
      // scope, so auto-registration and relative precache URLs don't apply.
      // The web manifest is served by Django at /manifest.webmanifest.
      registerType: 'prompt',
      injectRegister: false,
      devOptions: { enabled: false },
      manifest: false,
      filename: 'sw.js',
      workbox: {
        // Precache URLs must be absolute: the worker runs at root scope.
        manifestTransforms: [
          (entries) => ({
            manifest: entries.map((entry) => ({
              ...entry,
              url:
                entry.url === '/' || entry.url.startsWith('/static/web/')
                  ? entry.url
                  : `/static/web/${entry.url.replace(/^\//, '')}`,
            })),
            warnings: [],
          }),
        ],
        // '/' and icons are not build outputs; revision null refreshes them on SW updates.
        additionalManifestEntries: [
          { url: '/', revision: null },
          { url: '/static/web/pwa-192.png', revision: null },
          { url: '/static/web/pwa-512.png', revision: null },
          { url: '/static/web/maskable-512.png', revision: null },
          { url: '/static/web/apple-touch-icon.png', revision: null },
        ],
        navigateFallback: '/',
        navigateFallbackDenylist: [
          /^\/api\//,
          /^\/oauth\//,
          /^\/admin\//,
          /^\/static\//,
          /^\/media\//,
          /^\/healthz\//,
          /^\/sw\.js$/,
          /^\/manifest\.webmanifest$/,
        ],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: false,
        runtimeCaching: [
          {
            urlPattern: /\/static\/web\/assets\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'app-assets',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            urlPattern: /^https:\/\/image\.tmdb\.org\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'tmdb-images',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
        ],
      },
    }),
  ],
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
