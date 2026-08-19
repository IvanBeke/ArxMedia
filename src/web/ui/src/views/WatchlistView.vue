<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

    <div class="flex items-center justify-between mb-6">
      <h1 class="font-display text-2xl text-primary font-semibold">Watchlist</h1>
    </div>

    <MediaFilterBar
      :show-media-type-filter="true"
      :show-status-filter="false"
      :show-provider-status-filter="false"
      :show-genre-filter="true"
      :show-quick-filter-has-upcoming="false"
      :show-quick-filter-new-only="false"
      :show-quick-filter-missing-rating="false"
      :show-search="true"
      :show-sort="true"
      :show-direction="true"
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
          :watched="isWatchedStatus(item)"
          :status="item.user_status?.status || 'none'"
          :show-quick-action="canToggleWatchlist(item)"
          :quick-action-active="item.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH"
          :quick-action-loading="isLoading(item.media_type, item.tmdb_id)"
          :quick-action-pulsing="isPulsing(item.media_type, item.tmdb_id)"
          :quick-action-aria-label="getWatchlistAriaLabel(item.media_type, item.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH)"
          :show-watched-quick-action="true"
          :watched-quick-action-loading="isWatchedLoading(item.media_type, item.tmdb_id)"
          :watched-quick-action-pulsing="isWatchedPulsing(item.media_type, item.tmdb_id)"
          :watched-quick-action-aria-label="t('tracking_mark_as_watched')"
          :remove-watched-quick-action-aria-label="t('tracking_mark_as_watched')"
          :remove-watched-quick-action-confirm-text="getRemoveHistoryConfirmText(item.media_type)"
          @quick-action-watchlist="handleQuickAction(item, item.media_type)"
          @quick-action-watch-option="handleWatchOption(item, item.media_type, $event)"
          @quick-action-remove-watched="handleRemoveWatched(item, item.media_type)"
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
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import { useWatchlistQuickActions } from '@/composables/useWatchlistQuickActions'
import { useWatchedQuickActions } from '@/composables/useWatchedQuickActions'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'

const items = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const appliedFilters = ref({
  search: '',
  sort: 'added_at',
  direction: 'desc',
  mediaType: 'all',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
})
const currentPage = ref(1)
const totalPages = ref(1)
const count = ref(0)
const pageSize = ref(20)
const quickActionError = ref('')
const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const { showDatePicker, pickerInitialValue, pickWatchedDateTime, handleDatePickerConfirm, handleDatePickerCancel } = useWatchedDateTimePicker()
const { isLoading, isPulsing, toggleWatchlist } = useWatchlistQuickActions()
const { isLoading: isWatchedLoading, isPulsing: isWatchedPulsing, markWatched, unmarkWatched } = useWatchedQuickActions()

function canToggleWatchlist(item) {
  const status = item?.user_status?.status
  return status !== WATCH_ENTRY_STATUS.WATCHED && status !== WATCH_ENTRY_STATUS.WATCHING
}

function isWatchedStatus(item) {
  const status = item?.user_status?.status
  return status === WATCH_ENTRY_STATUS.WATCHED || status === WATCH_ENTRY_STATUS.WATCHING
}

function getWatchlistAriaLabel(mediaType, inWatchlist) {
  if (mediaType === MEDIA_TYPE.TV) {
    return inWatchlist ? t('watchlist_remove_show') : t('watchlist_add_show')
  }
  return inWatchlist ? t('watchlist_remove_movie') : t('watchlist_add_movie')
}

function getRemoveHistoryConfirmText(mediaType) {
  if (mediaType === MEDIA_TYPE.TV) {
    return t('remove_history_confirm_show')
  }
  return t('remove_history_confirm_movie')
}

function showQuickActionError(message) {
  quickActionError.value = message
  setTimeout(() => {
    quickActionError.value = ''
  }, 3500)
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

async function handleQuickAction(item, mediaType) {
  try {
    if (!canToggleWatchlist(item)) {
      return
    }

    const inWatchlist = item?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
    const result = await toggleWatchlist(mediaType, item.tmdb_id, inWatchlist)
    item.user_status = {
      ...(item.user_status || {}),
      status: result === 'removed' ? 'none' : WATCH_ENTRY_STATUS.PLAN_TO_WATCH,
    }

    if (result === 'removed') {
      items.value = items.value.filter(i => i.id !== item.id)
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watchlist.'))
  }
}

async function handleWatchOption(item, mediaType, option) {
  try {
    let watchedAt = null
    if (option === 'release') {
      const releaseDate = item.release_date || item.first_air_date
      watchedAt = releaseDate ? `${releaseDate}T00:00:00Z` : null
    } else if (option === 'date') {
      watchedAt = await pickWatchedDateTime(item?.user_status?.watched_at || '')
      if (!watchedAt) {
        return
      }
    }

    const nextStatus = await markWatched(mediaType, item.tmdb_id, watchedAt)
    if (!nextStatus) {
      return
    }

    const nowIso = watchedAt || new Date().toISOString()
    item.user_status = {
      ...(item.user_status || {}),
      status: nextStatus,
      watched_at: nowIso,
      status_changed_at: nowIso,
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watched status.'))
  }
}

async function handleRemoveWatched(item, mediaType) {
  try {
    const removed = await unmarkWatched(mediaType, item.tmdb_id)
    if (!removed) {
      return
    }

    item.user_status = {
      ...(item.user_status || {}),
      status: WATCH_ENTRY_STATUS.NONE,
      watched_at: null,
      status_changed_at: null,
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watched status.'))
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
