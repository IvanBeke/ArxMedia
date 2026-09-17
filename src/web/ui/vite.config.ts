import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      // App shell + fallback scope: precache the built shell, stay NetworkOnly for APIs.
      // The web manifest is served by Django at /manifest.webmanifest (single source of truth).
      // Registration is manual (see src/pwa/client.ts): the worker is emitted into
      // /static/web/ but served at /sw.js for root scope, so neither the plugin's
      // auto-registration nor its relative precache URLs would be correct as-is.
      registerType: 'prompt',
      injectRegister: false,
      devOptions: { enabled: false },
      manifest: false,
      filename: 'sw.js',
      workbox: {
        // Precache entries are relative to the emitted location (/static/web/);
        // rewrite them to absolute URLs because the worker runs at root scope.
        // '/' (navigateFallback target) and already-absolute URLs pass through.
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
        // The app shell ('/') and install icons are not build outputs, so they
        // are listed explicitly; revision null refreshes them on SW updates.
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
            // Lazy route chunks must work offline after first visit.
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
