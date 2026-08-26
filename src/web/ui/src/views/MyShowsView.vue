<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">My Shows</h1>
        <p class="text-muted text-sm">Track your shows and decide what to watch next.</p>
      </div>
      <div class="inline-flex items-center gap-2 rounded-full border border-surface-200 bg-surface-100 px-3 py-1 text-xs text-secondary">
        <span class="h-1.5 w-1.5 rounded-full bg-brand-500"></span>
        <span>{{ count }} shows | {{ watchedTimeLabel }}</span>
      </div>
    </div>

    <MediaFilterBar
      media-type="tv"
      :show-status-filter="true"
      :show-provider-status-filter="true"
      :show-genre-filter="true"
      :show-quick-filter-has-upcoming="true"
      :show-quick-filter-new-only="true"
      :show-quick-filter-missing-rating="true"
      :show-quick-filter-in-watchlist="false"
      :show-search="true"
      :show-sort="true"
      :show-direction="true"
      default-sort-key="time_left"
      search-placeholder="Search by show title"
      :provider-status-options="availableProviderStatuses"
      :genre-options="availableGenres"
      ref="filterBarRef"
      :page="currentPage"
      :sync-url="true"
      @change="onFilterBarChange"
    />

    <div v-if="loading" class="space-y-3">
      <div v-for="n in 8" :key="n" class="h-28 rounded-lg skeleton"></div>
    </div>

    <div v-else-if="rows.length" class="space-y-3 md:space-y-4">
      <ProgressRow
        v-for="item in rows"
        :key="item.tmdb_id"
        :item="item"
        @changed="loadMyShows"
        @error="onRowError"
      />

      <PaginationControls
        v-model:page="currentPage"
        :count="count"
        :loaded-count="lastLoadedCount"
        :max-visible-pages="10"
        :disabled="loading"
        @go="currentPage = $event"
      />
    </div>

    <div v-else class="card p-10 text-center">
      <p class="text-sm text-muted mb-3">No shows match your current filters.</p>
      <button class="btn-primary text-sm" @click="resetFilters">Clear filters</button>
    </div>

    <p v-if="errorMsg" class="mt-3 text-sm text-red-400">{{ errorMsg }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { trackingAPI } from '@/api'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import { getApiErrorMessage } from '@/utils/errors'
import { invalidPageRecovery, normalizePagedResponse } from '@/utils/pagination'
import { useQueryPageSync } from '@/composables/useQueryPageSync'
import { formatHoursMinutes } from '@/utils/progress'
import PaginationControls from '@/components/PaginationControls.vue'
import ProgressRow from '@/components/ProgressRow.vue'

const route = useRoute()

const loading = ref(true)
const rows = ref([])
const errorMsg = ref('')

const appliedFilters = ref({
  search: '',
  sort: 'time_left',
  direction: 'asc',
  mediaType: 'tv',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
  inWatchlist: false,
})

const availableGenres = ref([])
const availableProviderStatuses = ref([])

const count = ref(0)
const totalRuntimeMinutes = ref(0)
const currentPage = useQueryPageSync(route)
const lastLoadedCount = ref(0)
const filterBarRef = ref(null)
const hydrated = ref(false)

const watchedTimeLabel = computed(() => {
  return formatHoursMinutes(totalRuntimeMinutes.value)
})

function onFilterBarChange(payload) {
  const next = payload?.filters
  if (!next) return

  const didChange = JSON.stringify(appliedFilters.value) !== JSON.stringify(next)
  appliedFilters.value = next
  hydrated.value = true

  if (didChange && payload?.source === 'interaction') {
    currentPage.value = 1
  }
}

function buildParams() {
  const filterState = appliedFilters.value
  return {
    page: currentPage.value,
    sort: filterState.sort,
    direction: filterState.direction,
    ...(filterState.mediaType !== 'all' ? { media_type: filterState.mediaType } : {}),
    ...(filterState.search ? { search: filterState.search } : {}),
    ...(filterState.statuses.length ? { status: filterState.statuses } : {}),
    ...(filterState.providerStatuses.length ? { provider_status: filterState.providerStatuses } : {}),
    ...(filterState.hasUpcoming ? { has_upcoming: true } : {}),
    ...(filterState.newOnly ? { is_new: true } : {}),
    ...(filterState.missingRating ? { missing_rating: true } : {}),
    ...(filterState.genres.length ? { genres: filterState.genres } : {}),
  }
}

async function loadMyShows() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await trackingAPI.getMyShows(buildParams())
    const paged = normalizePagedResponse(data)
    rows.value = paged.items
    availableGenres.value = data?.available_genres || []
    availableProviderStatuses.value = data?.available_provider_statuses || []
    count.value = paged.count
    lastLoadedCount.value = paged.loadedCount
    totalRuntimeMinutes.value = Number.isFinite(data?.total_runtime_minutes) ? data.total_runtime_minutes : 0
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
    errorMsg.value = getApiErrorMessage(error, 'Could not load My Shows.')
  } finally {
    loading.value = false
  }
}

function onRowError(message) {
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
    await loadMyShows()
  },
  { deep: true, immediate: true }
)
</script>
