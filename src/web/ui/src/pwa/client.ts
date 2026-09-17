import { Workbox } from 'workbox-window'

export const SERVICE_WORKER_URL = '/sw.js'

/**
 * Create the update-aware service-worker client, or null when registration
 * must not happen (dev server, tests, unsupported browsers).
 *
 * The worker is emitted into /static/web/ by Vite but served at /sw.js so its
 * scope covers app navigations; registration is therefore manual instead of
 * using the plugin's auto-registration.
 */
export function createWorkbox(): Workbox | null {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return null
  if (!import.meta.env.PROD) return null
  try {
    return new Workbox(SERVICE_WORKER_URL, { scope: '/' })
  } catch {
    return null
  }
}
