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
    <div class="flex items-center gap-4 mb-6">
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
        <div class="flex items-center gap-3 py-4">
          <h2 class="text-sm font-medium text-secondary">{{ group.label }}</h2>
          <div class="flex-1 h-px bg-surface-200"></div>
          <span class="text-xs text-muted tab-selected px-2 py-0.5 rounded bg-surface-200">{{ group.items.length }}</span>
        </div>

        <!-- Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          <div
            v-for="entry in group.items"
            :key="entry.id"
            class="group relative"
          >
            <HistoryMediaCard
              :entry="entry"
              :link-to="getLink(entry)"
            />
            <button
              @click.prevent="deleteEntry(entry)"
              class="absolute top-2 right-2 p-1.5 bg-black/60 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/80 transition-all"
            >
              <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
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
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import PaginationControls from '@/components/PaginationControls.vue'

const route = useRoute()
const router = useRouter()

const entries = ref([])
const stats = ref(null)
const loading = ref(true)
const activeFilter = ref('all')
const sortOrder = ref('newest')
const currentPage = ref(1)
const totalPages = ref(1)
const count = ref(0)
const pageSize = ref(20)

const filters = [
  { label: 'All', value: 'all' },
  { label: 'Movies', value: MEDIA_TYPE.MOVIE },
  { label: 'Episodes', value: WATCH_ENTRY_MEDIA_TYPE.EPISODE },
]

const groupedEntries = computed(() => {
  const grouped = []
  const byKey = new Map()

  for (const entry of entries.value) {
    const dt = entry.watched_at ? new Date(entry.watched_at) : null
    const key = dt && !Number.isNaN(dt.getTime())
      ? dt.toISOString().slice(0, 10)
      : 'unknown'
    const label = dt && !Number.isNaN(dt.getTime())
      ? dt.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
      : 'Unknown date'

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
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) return `/tv/${entry.tmdb_id}/season/${entry.season_number}`
  return `/tv/${entry.tmdb_id}`
}

async function loadHistory() {
  loading.value = true
  try {
    const params = {
      order: sortOrder.value,
      page: currentPage.value,
    }
    if (activeFilter.value !== 'all') {
      params.media_type = activeFilter.value
    }

    const [historyRes, statsRes] = await Promise.all([
      trackingAPI.getHistory(params),
      trackingAPI.getStats()
    ])

    if (Array.isArray(historyRes?.results)) {
      count.value = Number.isFinite(historyRes.count) ? historyRes.count : historyRes.results.length
      if (historyRes.results.length > 0) {
        pageSize.value = historyRes.results.length
      }
      totalPages.value = Math.max(1, Math.ceil(count.value / pageSize.value))
    } else {
      const list = historyRes || []
      count.value = list.length
      totalPages.value = 1
    }

    entries.value = historyRes.results || historyRes
    stats.value = statsRes
  } catch (e) {
    console.error('Failed to load history', e)
  } finally {
    loading.value = false
  }
}

function queryToState() {
  const mediaType = route.query.media_type
  const order = route.query.order
  const pageQuery = Number.parseInt(String(route.query.page || ''), 10)

  const nextFilter = mediaType === MEDIA_TYPE.MOVIE || mediaType === WATCH_ENTRY_MEDIA_TYPE.EPISODE ? mediaType : 'all'
  const nextOrder = order === 'oldest' ? 'oldest' : 'newest'
  const nextPage = Number.isInteger(pageQuery) && pageQuery > 0 ? pageQuery : 1

  activeFilter.value = nextFilter
  sortOrder.value = nextOrder
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
  query.page = String(currentPage.value)
  return query
}

function syncUrlWithState() {
  const nextQuery = stateToQuery()
  const currentMediaType = route.query.media_type || undefined
  const currentOrder = route.query.order || undefined
  const currentPageQuery = route.query.page || undefined
  const nextMediaType = nextQuery.media_type || undefined
  const nextOrder = nextQuery.order || undefined
  const nextPageQuery = nextQuery.page || undefined

  if (currentMediaType === nextMediaType && currentOrder === nextOrder && currentPageQuery === nextPageQuery) {
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

function goToPage(page) {
  if (!Number.isInteger(page) || page < 1 || page > totalPages.value || page === currentPage.value || loading.value) {
    return
  }
  currentPage.value = page
}

async function deleteEntry(entry) {
  try {
    await trackingAPI.deleteHistory(entry.id)
    await loadHistory()
  } catch (e) {
    console.error('Failed to delete', e)
  }
}

watch([activeFilter, sortOrder, currentPage], syncUrlWithState)

watch(
  () => route.query,
  async () => {
    queryToState()
    await loadHistory()
  },
  { immediate: true }
)
</script>
