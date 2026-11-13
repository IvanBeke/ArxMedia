<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">{{ t('page_my_shows') }}</h1>
        <p class="text-muted text-sm">{{ t('my_shows_subtitle') }}</p>
      </div>
      <CountRuntimeBadge :count="count" :type-label="t('my_shows_type_label')" :total-minutes="totalRuntimeMinutes" />
    </div>

    <MediaFilterBar
      kind="library"
      media-type="tv"
      :search-placeholder="t('my_shows_search_placeholder')"
      :provider-status-options="availableProviderStatuses"
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
      <p class="text-sm text-muted mb-3">{{ t('my_shows_empty') }}</p>
      <button class="btn-primary text-sm" @click="resetFilters">{{ t('list_clear_filters') }}</button>
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
import { usePageTitle } from '@/composables/usePageTitle'
import { useI18n } from '@/i18n'

const { t } = useI18n()
usePageTitle(() => t('page_my_shows'))

interface ShowFilterState {
  search: string; sort: string; direction: string; mediaType: string; statuses: string[]
  providerStatuses: string[]; genres: string[]; hasUpcoming: boolean; newOnly: boolean
  missingRating: boolean; hasNextEpisode: boolean; inWatchlist: boolean
}
interface MediaListExtras { available_provider_statuses?: string[]; total_runtime_minutes?: number }

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
  loadErrorMessage: t('my_shows_load_failed'),
  onExtras: (data) => {
    const extras = data as typeof data & MediaListExtras
    availableProviderStatuses.value = extras.available_provider_statuses ?? []
  },
})
</script>
