import { getCurrentInstance, onBeforeUnmount } from 'vue'

/**
 * Runs `cleanup` before the component unmounts so pending timers or other
 * deferred work cannot fire after teardown. Safe to call outside setup
 * (e.g. in unit tests): without an active instance there is nothing to
 * hook into, so it becomes a no-op instead of warning.
 */
export function useCleanupOnUnmount(cleanup: () => void) {
  if (getCurrentInstance()) {
    onBeforeUnmount(cleanup)
  }
}
