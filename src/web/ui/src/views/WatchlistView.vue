<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

    <div class="flex items-center justify-between mb-6">
      <h1 class="font-display text-2xl text-primary font-semibold">Watchlist</h1>
    </div>

    <MediaFilterBar
      media-type="all"
      :show-status-filter="false"
      :show-provider-status-filter="false"
      :show-genre-filter="true"
      :show-quick-filter-has-upcoming="false"
      :show-quick-filter-new-only="false"
      :show-quick-filter-missing-rating="false"
      :show-quick-filter-in-watchlist="false"
      :show-search="true"
      :show-sort="true"
      :show-direction="true"
      default-sort-key="added_at"
      :apply-media-type-exclusive-sorts="false"
      search-placeholder="Search by title"
      ref="filterBarRef"
      :page="currentPage"
      :sync-url="true"
      @change="onFilterBarChange"
    />

    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <div v-for="n in 10" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
    </div>

    <div v-else-if="items.length">
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <MediaCard
          v-for="item in items"
          :key="`${item.media_type}-${item.id}`"
          :item="item"
          :media-type="item.media_type"
          @error="showQuickActionError"
          @watchlist-removed="handleWatchlistRemoved"
        />
      </div>
      <PaginationControls
        v-model:page="currentPage"
        :count="count"
        :loaded-count="lastLoadedCount"
        :max-visible-pages="10"
        :disabled="loadingMore"
        @go="currentPage = $event"
      />
    </div>

    <div v-if="!loading && !items.length" class="card p-10 text-center">
      <p class="text-gray-500 text-sm mb-3">Your watchlist is empty</p>
      <RouterLink to="/search" class="btn-primary text-sm">Find Something to Watch</RouterLink>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { trackingAPI } from '@/api'
import MediaCard from '@/components/MediaCard.vue'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import { useI18n } from '@/i18n'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { invalidPageRecovery, normalizePagedResponse } from '@/utils/pagination'
import { useQueryPageSync } from '@/composables/useQueryPageSync'

const items = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const appliedFilters = ref({
  search: '',
  sort: 'added_at',
  direction: 'asc',
  mediaType: 'all',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
  inWatchlist: false,
})
const count = ref(0)
const lastLoadedCount = ref(0)
const { errorMsg: quickActionError, showError: showQuickActionError } = useFlashMessages()
const { t } = useI18n()
const route = useRoute()
const filterBarRef = ref(null)
const currentPage = useQueryPageSync(route)

function handleWatchlistRemoved(payload) {
  const itemId = payload?.tmdb_id || payload?.id
  if (!itemId) {
    return
  }
  items.value = items.value.filter((entry) => {
    const entryId = entry.tmdb_id || entry.id
    return entryId !== itemId
  })
}

async function load() {
  const page = currentPage.value
  const showFullLoader = page === 1 || items.value.length === 0
  if (showFullLoader) {
    loading.value = true
  } else {
    loadingMore.value = true
  }
  const filterState = appliedFilters.value
  const params = {
    ...(filterState.mediaType !== 'all' ? { media_type: filterState.mediaType } : {}),
    ...(filterState.search ? { search: filterState.search } : {}),
    ...(filterState.genres.length ? { genres: filterState.genres } : {}),
    sort: filterState.sort,
    direction: filterState.direction,
    page,
  }
  try {
    const paged = normalizePagedResponse(await trackingAPI.getWatchlist(params))
    if (paged.items.length || paged.count) {
      count.value = paged.count
      lastLoadedCount.value = paged.loadedCount
      items.value = paged.items
    }
  } catch (error) {
    const recoveryPage = invalidPageRecovery(error, page)
    if (recoveryPage !== null) {
      currentPage.value = recoveryPage
      return
    }
    throw error
  } finally {
    if (showFullLoader) {
      loading.value = false
    } else {
      loadingMore.value = false
    }
  }
}

function resetPage() {
  currentPage.value = 1
  count.value = 0
}

function onFilterBarChange(payload) {
  const next = payload?.filters
  if (!next) return
  const didChange = JSON.stringify(appliedFilters.value) !== JSON.stringify(next)
  appliedFilters.value = next
  if (didChange && payload?.source === 'interaction') {
    resetPage()
  }
}

watch(
  [appliedFilters, currentPage],
  async () => {
    await load()
  },
  { deep: true, immediate: true }
)
</script>
