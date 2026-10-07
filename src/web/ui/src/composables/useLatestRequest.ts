import { onBeforeUnmount } from 'vue'

/** True when a request failed only because a newer one (or unmounting) cancelled it. */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

/**
 * Keeps only the latest request alive: `next()` cancels the previous request and
 * returns a fresh signal, so an older response can never overwrite newer results.
 */
export function useLatestRequest() {
  let controller: AbortController | null = null

  function next(): AbortSignal {
    controller?.abort()
    controller = new AbortController()
    return controller.signal
  }

  onBeforeUnmount(() => controller?.abort())

  return { next }
}
