import { reactive, ref, watch, type Ref } from 'vue'
import type { ApiError } from '@/types/api'

interface StatsSectionOptions {
  /** Hold off fetching (and clear the data) while this is false. */
  enabled?: () => boolean
  /** Something besides the username the fetcher depends on, such as a year: a change reloads like a new username. */
  refreshOn?: () => unknown
}

/**
 * Loads one stats endpoint for a profile and tracks its loading, error and
 * forbidden (private profile) states. It loads when the username changes,
 * dropping the previous profile's data, and ignores responses that a newer
 * request has made stale. `load()` fetches again but keeps the current data on
 * screen until the new data arrives, which suits retrying, refreshing and
 * changing a value the section depends on (such as the year).
 */
export function useStatsSection<T>(
  username: () => string,
  fetcher: (username: string) => Promise<T>,
  { enabled = () => true, refreshOn = () => undefined }: StatsSectionOptions = {},
) {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref(false)
  const forbidden = ref(false)
  let latest = 0

  async function load() {
    const ticket = ++latest
    error.value = false
    forbidden.value = false
    if (!enabled() || !username()) {
      loading.value = false
      return
    }
    loading.value = true
    try {
      const result = await fetcher(username())
      if (ticket === latest) data.value = result
    } catch (caught: unknown) {
      if (ticket !== latest) return
      if ((caught as ApiError).status === 403) forbidden.value = true
      else error.value = true
    } finally {
      if (ticket === latest) loading.value = false
    }
  }

  // One watcher for all dependencies: two watchers would double-load when, for example, a year becoming available
  // also flips `enabled`. Only a new profile clears the previous data; a year change keeps it on screen.
  let loadedUsername: string | undefined
  watch([username, enabled, refreshOn], () => {
    if (loadedUsername !== username()) data.value = null
    loadedUsername = username()
    return load()
  }, { immediate: true })

  return reactive({ data, loading, error, forbidden, load })
}

/** Reloads only the sections whose last request failed. */
export function retryFailed(...sections: { error: boolean; load: () => Promise<void> }[]) {
  for (const section of sections) {
    if (section.error) void section.load()
  }
}
