import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getApiErrorMessage } from '@/utils/errors'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'
import { invalidPageRecovery, normalizePagedResponse } from '@/utils/pagination'
import { useQueryPageSync } from '@/composables/useQueryPageSync'
import type { QueryParams } from '@/types/api'

export interface FilterChange<F> {
  filters: F
  source: 'hydrate' | 'interaction'
}

/**
 * Filter bar + paged loading shared by the "my library" list views.
 * `toParams` maps the view's filter state to API params; `onExtras`
 * receives the raw response for view-specific extras (genre options, ...).
 */
export function usePagedFilteredList<T, F extends object>(options: {
  fetcher: (params: QueryParams, request: { signal: AbortSignal }) => Promise<unknown>
  initialFilters: F
  toParams: (filters: F, page: number) => QueryParams
  loadErrorMessage: string
  onExtras?: (data: unknown) => void
}) {
  const route = useRoute()

  const loading = ref(true)
  const rows = ref<T[]>([])
  const errorMsg = ref('')
  const appliedFilters = ref<F>({ ...options.initialFilters })
  const count = ref(0)
  const totalRuntimeMinutes = ref(0)
  const currentPage = useQueryPageSync(route)
  const lastLoadedCount = ref(0)
  const filterBarRef = ref<{ clearAll: () => void } | null>(null)
  const hydrated = ref(false)
  const latestRequest = useLatestRequest()

  function onFilterBarChange(payload: FilterChange<F>) {
    const next = payload.filters

    const didChange = JSON.stringify(appliedFilters.value) !== JSON.stringify(next)
    appliedFilters.value = next
    hydrated.value = true

    if (didChange && payload.source === 'interaction') {
      currentPage.value = 1
    }
  }

  async function load() {
    const signal = latestRequest.next()
    loading.value = true
    errorMsg.value = ''
    try {
      const data = await options.fetcher(options.toParams(appliedFilters.value, currentPage.value), { signal })
      const paged = normalizePagedResponse<T>(data)
      rows.value = paged.items
      const minutes = (data as { total_runtime_minutes?: unknown } | null)?.total_runtime_minutes
      totalRuntimeMinutes.value = typeof minutes === 'number' && Number.isFinite(minutes) ? minutes : 0
      options.onExtras?.(data)
      count.value = paged.count
      lastLoadedCount.value = paged.loadedCount
    } catch (error) {
      if (isAbortError(error)) return
      const recoveryPage = invalidPageRecovery(error, currentPage.value)
      if (recoveryPage !== null) {
        currentPage.value = recoveryPage
        return
      }
      rows.value = []
      count.value = 0
      totalRuntimeMinutes.value = 0
      lastLoadedCount.value = 0
      errorMsg.value = getApiErrorMessage(error, options.loadErrorMessage)
    } finally {
      if (!signal.aborted) loading.value = false
    }
  }

  function onRowError(message: string) {
    errorMsg.value = message
  }

  function resetFilters() {
    filterBarRef.value?.clearAll()
  }

  onMounted(() => {
    if (!hydrated.value) hydrated.value = true
  })

  watch(
    [appliedFilters, currentPage, hydrated],
    async () => {
      if (!hydrated.value) return
      await load()
    },
    { deep: true, immediate: true },
  )

  return {
    loading, rows, errorMsg, appliedFilters, count, totalRuntimeMinutes,
    currentPage, lastLoadedCount, filterBarRef, hydrated,
    onFilterBarChange, load, onRowError, resetFilters,
  }
}
