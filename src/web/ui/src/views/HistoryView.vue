<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="font-display text-2xl text-primary font-semibold">History</h1>
      <div class="text-sm text-muted">
        <span class="text-brand-400 font-medium">{{ stats?.movies_watched || 0 }}</span> movies · 
        <span class="text-brand-400 font-medium">{{ stats?.episodes_watched || 0 }}</span> episodes
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap items-center gap-4 mb-6">
      <div class="flex gap-1 bg-surface-200 rounded-md p-1">
        <button
          v-for="t in filters"
          :key="t.value"
          @click="setFilter(t.value)"
          class="px-3 py-1.5 rounded text-xs font-medium transition-colors"
          :class="activeFilter === t.value ? 'bg-brand-500 text-white' : 'text-muted hover:text-primary'"
        >
          {{ t.label }}
        </button>
      </div>
      <button
        @click="toggleSort"
        class="text-xs text-muted hover:text-primary flex items-center gap-1"
      >
        <span>{{ sortOrder === 'newest' ? 'Newest' : 'Oldest' }} first</span>
        <svg class="w-3 h-3" :class="{ 'rotate-180': sortOrder === 'oldest' }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/>
        </svg>
      </button>
      <button
        type="button"
        class="group-toggle ml-auto"
        :data-on="groupByDay ? 'true' : 'false'"
        :aria-pressed="groupByDay"
        aria-label="Group by day"
        @click="toggleDayGrouping"
      >
        <span class="group-toggle-pill">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10m-12 9h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v11a2 2 0 002 2z" />
          </svg>
          <span class="group-toggle-label">Group by day</span>
        </span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3">
      <div v-for="n in 8" :key="n" class="flex gap-4">
        <div class="w-24 h-36 skeleton rounded-lg flex-shrink-0"></div>
        <div class="flex-1 h-36 skeleton rounded-lg"></div>
      </div>
    </div>

    <!-- History List -->
    <div v-else-if="entries.length" class="space-y-6">
      <template v-for="group in groupedEntries" :key="group.label">
        <!-- Date Header -->
        <div v-if="groupByDay" class="flex items-center gap-3 py-4">
          <h2 class="text-sm font-medium text-secondary">{{ group.label }}</h2>
          <div class="flex-1 h-px bg-surface-200"></div>
          <span class="text-xs text-muted tab-selected px-2 py-0.5 rounded bg-surface-200">{{ group.items.length }}</span>
        </div>

        <!-- Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          <HistoryMediaCard
            v-for="entry in group.items"
            :key="entry.id"
            :entry="entry"
            :link-to="getLink(entry)"
            :show-remove-action="true"
            :remove-loading="deletingEntryId === entry.id"
            :remove-confirm-text="getRemoveHistoryConfirmText(entry)"
            @action:history-remove="deleteEntry"
          />
        </div>
      </template>

      <PaginationControls
        :current-page="currentPage"
        :total-pages="totalPages"
        :max-visible-pages="10"
        :disabled="loading"
        @go="goToPage"
      />
    </div>

    <!-- Empty -->
    <div v-else class="card p-16 text-center">
      <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-surface-200 flex items-center justify-center">
        <svg class="w-8 h-8 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <p class="text-muted mb-4">No watch history yet</p>
      <RouterLink to="/search" class="btn-primary">Start Watching</RouterLink>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { trackingAPI } from '@/api'
import { MEDIA_TYPE, WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import { formatTemporalDate, isoDateKey } from '@/utils/temporal'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const entries = ref([])
const stats = ref(null)
const loading = ref(true)
const activeFilter = ref('all')
const sortOrder = ref('newest')
const groupByDay = ref(true)
const currentPage = ref(1)
const totalPages = ref(1)
const count = ref(0)
const pageSize = ref(20)
const deletingEntryId = ref(null)
let suppressRouteLoad = false

const filters = [
  { label: 'All', value: 'all' },
  { label: 'Movies', value: MEDIA_TYPE.MOVIE },
  { label: 'Episodes', value: WATCH_ENTRY_MEDIA_TYPE.EPISODE },
]

const groupedEntries = computed(() => {
  if (!groupByDay.value) {
    return [{ key: 'all', label: 'All entries', items: entries.value }]
  }

  const grouped = []
  const byKey = new Map()

  for (const entry of entries.value) {
    const key = isoDateKey(entry.watched_at) || 'unknown'
    const label = key === 'unknown'
      ? 'Unknown date'
      : formatTemporalDate(entry.watched_at, 'en-US', { month: 'long', day: 'numeric', year: 'numeric' })

    if (!byKey.has(key)) {
      const group = { key, label, items: [] }
      byKey.set(key, group)
      grouped.push(group)
    }
    byKey.get(key).items.push(entry)
  }

  return grouped
})

function getLink(entry) {
  if (entry.media_type === MEDIA_TYPE.MOVIE) return `/movies/${entry.tmdb_id}`
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return `/tv/${entry.tmdb_id}/season/${entry.season_number}/episode/${entry.episode_number}`
  }
  return `/tv/${entry.tmdb_id}`
}

function getRemoveHistoryConfirmText(entry) {
  if (entry?.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return t('remove_history_confirm_episode')
  }
  return t('remove_history_confirm_movie')
}

function decrementHistoryStats(currentStats, mediaType) {
  if (!currentStats) return currentStats

  if (mediaType === MEDIA_TYPE.MOVIE) {
    return {
      ...currentStats,
      movies_watched: Math.max(0, Number(currentStats.movies_watched || 0) - 1),
    }
  }

  if (mediaType === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return {
      ...currentStats,
      episodes_watched: Math.max(0, Number(currentStats.episodes_watched || 0) - 1),
    }
  }

  return currentStats
}

async function loadHistory() {
  loading.value = true
  try {
    const [historyRes, statsRes] = await Promise.all([
      trackingAPI.getHistory(buildHistoryParams()),
      trackingAPI.getStats()
    ])
    applyHistoryResponse(historyRes)
    stats.value = statsRes
  } catch (e) {
    console.error('Failed to load history', e)
  } finally {
    loading.value = false
  }
}

function buildHistoryParams(page = currentPage.value) {
  const params = {
    order: sortOrder.value,
    page,
  }
  if (activeFilter.value !== 'all') {
    params.media_type = activeFilter.value
  }
  return params
}

function applyHistoryResponse(historyRes) {
  if (Array.isArray(historyRes?.results)) {
    count.value = Number.isFinite(historyRes.count) ? historyRes.count : historyRes.results.length
    if (historyRes.results.length > 0) {
      pageSize.value = historyRes.results.length
    }
    totalPages.value = Math.max(1, Math.ceil(count.value / pageSize.value))
    entries.value = historyRes.results
    return
  }

  const list = historyRes || []
  count.value = list.length
  totalPages.value = 1
  entries.value = list
}

async function loadHistoryEntries(page = currentPage.value) {
  const historyRes = await trackingAPI.getHistory(buildHistoryParams(page))
  applyHistoryResponse(historyRes)
}

function queryToState() {
  const mediaType = route.query.media_type
  const order = route.query.order
  const groupByDayQuery = route.query.group_by_day
  const pageQuery = Number.parseInt(String(route.query.page || ''), 10)

  const nextFilter = mediaType === MEDIA_TYPE.MOVIE || mediaType === WATCH_ENTRY_MEDIA_TYPE.EPISODE ? mediaType : 'all'
  const nextOrder = order === 'oldest' ? 'oldest' : 'newest'
  const nextGroupByDay = groupByDayQuery !== '0'
  const nextPage = Number.isInteger(pageQuery) && pageQuery > 0 ? pageQuery : 1

  activeFilter.value = nextFilter
  sortOrder.value = nextOrder
  groupByDay.value = nextGroupByDay
  currentPage.value = nextPage
}

function stateToQuery() {
  const query = {}
  if (activeFilter.value !== 'all') {
    query.media_type = activeFilter.value
  }
  if (sortOrder.value !== 'newest') {
    query.order = sortOrder.value
  }
  if (!groupByDay.value) {
    query.group_by_day = '0'
  }
  query.page = String(currentPage.value)
  return query
}

function syncUrlWithState() {
  const nextQuery = stateToQuery()
  const currentMediaType = route.query.media_type || undefined
  const currentOrder = route.query.order || undefined
  const currentGroupByDay = route.query.group_by_day || undefined
  const currentPageQuery = route.query.page || undefined
  const nextMediaType = nextQuery.media_type || undefined
  const nextOrder = nextQuery.order || undefined
  const nextGroupByDay = nextQuery.group_by_day || undefined
  const nextPageQuery = nextQuery.page || undefined

  if (
    currentMediaType === nextMediaType &&
    currentOrder === nextOrder &&
    currentGroupByDay === nextGroupByDay &&
    currentPageQuery === nextPageQuery
  ) {
    return
  }

  router.replace({ query: nextQuery })
}

function setFilter(nextFilter) {
  if (activeFilter.value === nextFilter && currentPage.value === 1) {
    return
  }
  activeFilter.value = nextFilter
  currentPage.value = 1
}

function toggleSort() {
  sortOrder.value = sortOrder.value === 'newest' ? 'oldest' : 'newest'
  currentPage.value = 1
}

function toggleDayGrouping() {
  groupByDay.value = !groupByDay.value
}

function goToPage(page) {
  if (!Number.isInteger(page) || page < 1 || page > totalPages.value || page === currentPage.value || loading.value) {
    return
  }
  currentPage.value = page
}

async function deleteEntry(entry) {
  if (deletingEntryId.value) {
    return
  }
  deletingEntryId.value = entry.id

  try {
    await trackingAPI.deleteHistory(entry.id)
    const nextPage = entries.value.length === 1 && currentPage.value > 1
      ? currentPage.value - 1
      : currentPage.value

    if (nextPage !== currentPage.value) {
      suppressRouteLoad = true
      currentPage.value = nextPage
    }

    await loadHistoryEntries(nextPage)
    stats.value = decrementHistoryStats(stats.value, entry.media_type)
  } catch (e) {
    console.error('Failed to delete', e)
  } finally {
    deletingEntryId.value = null
  }
}

watch([activeFilter, sortOrder, groupByDay, currentPage], syncUrlWithState)

watch(
  () => route.query,
  async () => {
    if (suppressRouteLoad) {
      suppressRouteLoad = false
      return
    }
    queryToState()
    await loadHistory()
  },
  { immediate: true }
)
</script>

<style scoped>
.group-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.group-toggle-label {
  white-space: nowrap;
}

.group-toggle-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-radius: 9999px;
  border: 1px solid var(--filter-chip-border);
  background: var(--filter-chip-bg);
  color: var(--filter-chip-text);
  padding: 0.33rem 0.58rem;
  transition: background-color 0.22s ease, border-color 0.22s ease, color 0.22s ease;
}

.group-toggle[data-on='true'] .group-toggle-pill {
  border-color: var(--filter-chip-active-border);
  background: var(--filter-chip-active-bg);
  color: var(--filter-chip-active-text);
}

.group-toggle:focus-visible .group-toggle-pill {
  outline: 2px solid color-mix(in srgb, var(--brand-400) 75%, white 25%);
  outline-offset: 2px;
}
</style>
