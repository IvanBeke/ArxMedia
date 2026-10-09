<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">My Shows</h1>
        <p class="text-muted text-sm">Track your shows and decide what to watch next.</p>
      </div>
      <CountRuntimeBadge :count="count" type-label="shows" :total-minutes="totalRuntimeMinutes" />
    </div>

    <MediaFilterBar
      media-type="tv"
      :show-status-filter="true"
      :show-provider-status-filter="true"
      :show-genre-filter="true"
      :show-quick-filter-has-upcoming="true"
      :show-quick-filter-new-only="true"
      :show-quick-filter-missing-rating="true"
      :show-quick-filter-has-next-episode="true"
      :show-quick-filter-in-watchlist="false"
      :show-search="true"
      :show-sort="true"
      :show-direction="true"
      :show-provider-rating-sort="true"
      :show-user-rating-sort="true"
      default-sort-key="last_watched"
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

<script setup lang="ts">
import { ref } from 'vue'
import { trackingAPI } from '@/api'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import CountRuntimeBadge from '@/components/CountRuntimeBadge.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import ProgressRow from '@/components/ProgressRow.vue'
import { usePagedFilteredList } from '@/composables/usePagedFilteredList'
import type { QueryParams, ShowProgressItem } from '@/types/api'

interface ShowFilterState {
  search: string; sort: string; direction: string; mediaType: string; statuses: string[]
  providerStatuses: string[]; genres: string[]; hasUpcoming: boolean; newOnly: boolean
  missingRating: boolean; hasNextEpisode: boolean; inWatchlist: boolean
}
interface MediaListExtras { available_genres?: string[]; available_provider_statuses?: string[]; total_runtime_minutes?: number }

const availableGenres = ref<string[]>([])
const availableProviderStatuses = ref<string[]>([])

const {
  loading, rows, errorMsg, count, totalRuntimeMinutes, currentPage, lastLoadedCount,
  filterBarRef, onFilterBarChange, load: loadMyShows, onRowError, resetFilters,
} = usePagedFilteredList<ShowProgressItem, ShowFilterState>({
  fetcher: (params, request) => trackingAPI.getMyShows(params, request),
  initialFilters: {
    search: '',
    sort: 'last_watched',
    direction: 'desc',
    mediaType: 'tv',
    statuses: [],
    providerStatuses: [],
    genres: [],
    hasUpcoming: false,
    newOnly: false,
    missingRating: false,
    hasNextEpisode: false,
    inWatchlist: false,
  },
  toParams: (filterState, page): QueryParams => ({
    page,
    sort: filterState.sort,
    direction: filterState.direction,
    ...(filterState.mediaType !== 'all' ? { media_type: filterState.mediaType } : {}),
    ...(filterState.search ? { search: filterState.search } : {}),
    ...(filterState.statuses.length ? { status: filterState.statuses } : {}),
    ...(filterState.providerStatuses.length ? { provider_status: filterState.providerStatuses } : {}),
    ...(filterState.hasUpcoming ? { has_upcoming: true } : {}),
    ...(filterState.newOnly ? { is_new: true } : {}),
    ...(filterState.missingRating ? { missing_rating: true } : {}),
    ...(filterState.hasNextEpisode ? { has_next_episode: true } : {}),
    ...(filterState.genres.length ? { genres: filterState.genres } : {}),
  }),
  loadErrorMessage: 'Could not load My Shows.',
  onExtras: (data) => {
    const extras = data as typeof data & MediaListExtras
    availableGenres.value = extras.available_genres ?? []
    availableProviderStatuses.value = extras.available_provider_statuses ?? []
  },
})
</script>
