import { Workbox } from 'workbox-window'

export const SERVICE_WORKER_URL = '/sw.js'

/** Update-aware SW client, or null where registration must not happen. */
export function createWorkbox(): Workbox | null {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return null
  if (!import.meta.env.PROD) return null
  try {
    return new Workbox(SERVICE_WORKER_URL, { scope: '/' })
  } catch {
    return null
  }
}
