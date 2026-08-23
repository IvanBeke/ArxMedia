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
        :current-page="currentPage"
        :total-pages="totalPages"
        :max-visible-pages="10"
        :disabled="loadingMore"
        @go="goToPage"
      />
    </div>

    <div v-if="!loading && !items.length" class="card p-10 text-center">
      <p class="text-gray-500 text-sm mb-3">Your watchlist is empty</p>
      <RouterLink to="/search" class="btn-primary text-sm">Find Something to Watch</RouterLink>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { trackingAPI } from '@/api'
import MediaCard from '@/components/MediaCard.vue'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import { useI18n } from '@/i18n'
import { useFlashMessages } from '@/composables/useFlashMessages'

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
const currentPage = ref(1)
const totalPages = ref(1)
const count = ref(0)
const pageSize = ref(20)
const { errorMsg: quickActionError, showError: showQuickActionError } = useFlashMessages()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()

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

async function load(page = 1) {
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
    const data = await trackingAPI.getWatchlist(params)
    if (data) {
      const pageItems = data.results || data
      if (Array.isArray(data.results)) {
        count.value = Number.isFinite(data.count) ? data.count : data.results.length
        if (page === 1 && data.results.length > 0) {
          pageSize.value = data.results.length
        }
        totalPages.value = Math.max(1, Math.ceil(count.value / pageSize.value))
      } else {
        count.value = pageItems.length
        totalPages.value = 1
      }
      if (page === 1) {
        items.value = pageItems
      } else {
        items.value = pageItems
      }
      currentPage.value = page
      syncPageQuery()
    }
  } finally {
    if (showFullLoader) {
      loading.value = false
    } else {
      loadingMore.value = false
    }
  }
}

async function goToPage(page) {
  if (!Number.isInteger(page) || page < 1 || page > totalPages.value || page === currentPage.value || loading.value || loadingMore.value) {
    return
  }
  await load(page)
}

function resetPage() {
  totalPages.value = 1
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

function parsePage(value) {
  const page = Number.parseInt(String(value || ''), 10)
  return Number.isInteger(page) && page > 0 ? page : 1
}

function syncPageQuery() {
  const nextQuery = {
    ...route.query,
    page: String(currentPage.value),
  }
  if (JSON.stringify(route.query) !== JSON.stringify(nextQuery)) {
    router.replace({ query: nextQuery })
  }
}

onMounted(async () => {
  currentPage.value = parsePage(route.query.page)
  await load(currentPage.value)
})

watch(
  [appliedFilters, currentPage],
  async () => {
    syncPageQuery()
    await load(currentPage.value)
  },
  { deep: true }
)

watch(
  () => route.query.page,
  async () => {
    const nextPage = parsePage(route.query.page)
    if (nextPage === currentPage.value) return
    currentPage.value = nextPage
    await load(currentPage.value)
  }
)

</script>
