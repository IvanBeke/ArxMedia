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
      :show-provider-rating-sort="true"
      :show-user-rating-sort="true"
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
import { ref } from 'vue'
import { trackingAPI } from '@/api'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import MovieRow from '@/components/MovieRow.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import CountRuntimeBadge from '@/components/CountRuntimeBadge.vue'
import { usePagedFilteredList } from '@/composables/usePagedFilteredList'
import type { MediaCard, QueryParams } from '@/types/api'

interface MovieFilterState { search: string; sort: string; direction: string; mediaType: string; statuses: string[]; genres: string[]; missingRating: boolean }
interface MediaListExtras { available_genres?: string[]; total_runtime_minutes?: number }
type MovieRowItem = MediaCard & { genres?: string[]; runtime?: number | null; last_watched_at?: string | null; user_rating?: number | null }

const availableGenres = ref<string[]>([])

const {
  loading, rows, errorMsg, count, totalRuntimeMinutes, currentPage, lastLoadedCount,
  filterBarRef, onFilterBarChange, load: loadMyMovies, onRowError, resetFilters,
} = usePagedFilteredList<MovieRowItem, MovieFilterState>({
  fetcher: (params, request) => trackingAPI.getMyMovies(params, request),
  initialFilters: {
    search: '',
    sort: 'watched_date',
    direction: 'desc',
    mediaType: 'movie',
    statuses: [],
    genres: [],
    missingRating: false,
  },
  toParams: (filterState, page): QueryParams => ({
    page,
    sort: filterState.sort,
    direction: filterState.direction,
    ...(filterState.mediaType !== 'all' ? { media_type: filterState.mediaType } : {}),
    ...(filterState.search ? { search: filterState.search } : {}),
    ...(filterState.statuses.length ? { status: filterState.statuses } : {}),
    ...(filterState.missingRating ? { missing_rating: true } : {}),
    ...(filterState.genres.length ? { genres: filterState.genres } : {}),
  }),
  loadErrorMessage: 'Could not load My Movies.',
  onExtras: (data) => {
    availableGenres.value = (data as typeof data & MediaListExtras).available_genres ?? []
  },
})
</script>
