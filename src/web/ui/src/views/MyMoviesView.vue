<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">My Movies</h1>
        <p class="text-muted text-sm">Track your movies and decide what to watch next.</p>
      </div>
      <CountRuntimeBadge :count="count" type-label="movies" :total-minutes="totalRuntimeMinutes" />
    </div>

    <MediaFilterBar
      media-type="movie"
      :show-status-filter="true"
      :show-provider-status-filter="false"
      :show-genre-filter="true"
      :show-quick-filter-has-upcoming="false"
      :show-quick-filter-new-only="false"
      :show-quick-filter-missing-rating="true"
      :show-quick-filter-in-watchlist="false"
      :show-search="true"
      :show-sort="true"
      :show-direction="true"
      default-sort-key="watched_date"
      search-placeholder="Search by movie title"
      :genre-options="availableGenres"
      ref="filterBarRef"
      :page="currentPage"
      :sync-url="true"
      @change="onFilterBarChange"
    />

    <div v-if="loading" class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div v-for="n in 8" :key="n" class="h-28 rounded-lg skeleton"></div>
    </div>

    <template v-else-if="rows.length">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <MovieRow
          v-for="item in rows"
          :key="item.tmdb_id"
          :item="item"
          @changed="loadMyMovies"
          @error="onRowError"
        />
      </div>

      <PaginationControls
        v-model:page="currentPage"
        :count="count"
        :loaded-count="lastLoadedCount"
        :max-visible-pages="10"
        :disabled="loading"
        @go="currentPage = $event"
      />
    </template>

    <div v-else class="card p-10 text-center">
      <p class="text-sm text-muted mb-3">No movies match your current filters.</p>
      <button class="btn-primary text-sm" @click="resetFilters">Clear filters</button>
    </div>

    <p v-if="errorMsg" class="mt-3 text-sm text-red-400">{{ errorMsg }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { trackingAPI } from '@/api'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import MovieRow from '@/components/MovieRow.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import CountRuntimeBadge from '@/components/CountRuntimeBadge.vue'
import { getApiErrorMessage } from '@/utils/errors'
import { invalidPageRecovery, normalizePagedResponse } from '@/utils/pagination'
import { useQueryPageSync } from '@/composables/useQueryPageSync'
import type { MediaCard, QueryParams } from '@/types/api'

interface MovieFilterState { search: string; sort: string; direction: string; mediaType: string; statuses: string[]; genres: string[]; missingRating: boolean }
interface FilterChange { filters: MovieFilterState; source: 'hydrate' | 'interaction' }
interface MediaListExtras { available_genres?: string[]; total_runtime_minutes?: number }
type MovieRowItem = MediaCard & { genres?: string[]; runtime?: number | null; last_watched_at?: string | null; user_rating?: number | null }

const route = useRoute()

const loading = ref(true)
const rows = ref<MovieRowItem[]>([])
const errorMsg = ref('')

const appliedFilters = ref<MovieFilterState>({
  search: '',
  sort: 'watched_date',
  direction: 'desc',
  mediaType: 'movie',
  statuses: [],
  genres: [],
  missingRating: false,
})

const availableGenres = ref<string[]>([])

const count = ref(0)
const totalRuntimeMinutes = ref(0)
const currentPage = useQueryPageSync(route)
const lastLoadedCount = ref(0)
const filterBarRef = ref<{ clearAll: () => void } | null>(null)
const hydrated = ref(false)

function onFilterBarChange(payload: FilterChange) {
  const next = payload.filters

  const didChange = JSON.stringify(appliedFilters.value) !== JSON.stringify(next)
  appliedFilters.value = next
  hydrated.value = true

  if (didChange && payload.source === 'interaction') {
    currentPage.value = 1
  }
}

function buildParams(): QueryParams {
  const filterState = appliedFilters.value
  return {
    page: currentPage.value,
    sort: filterState.sort,
    direction: filterState.direction,
    ...(filterState.mediaType !== 'all' ? { media_type: filterState.mediaType } : {}),
    ...(filterState.search ? { search: filterState.search } : {}),
    ...(filterState.statuses.length ? { status: filterState.statuses } : {}),
    ...(filterState.missingRating ? { missing_rating: true } : {}),
    ...(filterState.genres.length ? { genres: filterState.genres } : {}),
  }
}

async function loadMyMovies() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await trackingAPI.getMyMovies(buildParams())
    const paged = normalizePagedResponse<MovieRowItem>(data)
    rows.value = paged.items
    const extras = data as typeof data & MediaListExtras
    availableGenres.value = extras.available_genres ?? []
    count.value = paged.count
    lastLoadedCount.value = paged.loadedCount
    totalRuntimeMinutes.value = Number.isFinite(extras.total_runtime_minutes) ? extras.total_runtime_minutes ?? 0 : 0
  } catch (error) {
    const recoveryPage = invalidPageRecovery(error, currentPage.value)
    if (recoveryPage !== null) {
      currentPage.value = recoveryPage
      return
    }
    rows.value = []
    count.value = 0
    totalRuntimeMinutes.value = 0
    lastLoadedCount.value = 0
    errorMsg.value = getApiErrorMessage(error, 'Could not load My Movies.')
  } finally {
    loading.value = false
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
    await loadMyMovies()
  },
  { deep: true, immediate: true }
)
</script>
