<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <h1 class="font-display text-2xl text-primary font-semibold mb-6">Discover</h1>

    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

    <!-- Search bar -->
    <div class="relative mb-6">
      <input
        v-model="query"
        @input="debouncedSearch"
        placeholder="Search for movies, TV shows..."
        class="input pl-12 py-3 rounded-md"
        autofocus
      />
      <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
      </svg>
      <button v-if="query" @click="query = ''; results = []" class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-primary">
        ✕
      </button>
    </div>

    <!-- Filters -->
    <div class="flex gap-1 mb-8">
      <button
        v-for="t in filters"
        :key="t.value"
        @click="activeFilter = t.value; debouncedSearch()"
        type="button"
        :aria-pressed="activeFilter === t.value ? 'true' : 'false'"
        class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
        :class="activeFilter === t.value ? 'bg-brand-500 text-white' : 'text-gray-400 hover:text-primary hover:bg-surface-100'"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <div v-for="n in 10" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
    </div>

    <!-- Results -->
    <div v-else-if="results.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <MediaCard
        v-for="item in results"
        :key="`${item.media_type}-${item.id}`"
        :item="item"
        :media-type="item.media_type || MEDIA_TYPE.MOVIE"
        :watched="isWatchedStatus(item)"
        :status="item.user_status?.status || 'none'"
        :show-quick-action="auth.isAuthenticated && canToggleWatchlist(item)"
        :quick-action-active="item.user_status?.status === 'plan_to_watch'"
        :quick-action-loading="isLoading(item.media_type || MEDIA_TYPE.MOVIE, item.id)"
        :quick-action-pulsing="isPulsing(item.media_type || MEDIA_TYPE.MOVIE, item.id)"
        :quick-action-aria-label="getWatchlistAriaLabel(item.media_type || MEDIA_TYPE.MOVIE, item.user_status?.status === 'plan_to_watch')"
        :show-watched-quick-action="auth.isAuthenticated"
        :watched-quick-action-loading="isWatchedLoading(item.media_type || MEDIA_TYPE.MOVIE, item.id)"
        :watched-quick-action-pulsing="isWatchedPulsing(item.media_type || MEDIA_TYPE.MOVIE, item.id)"
        :watched-quick-action-aria-label="t('tracking_mark_as_watched')"
        @quick-action-watchlist="handleQuickAction(item, item.media_type || MEDIA_TYPE.MOVIE)"
        @quick-action-watch-option="handleWatchOption(item, item.media_type || MEDIA_TYPE.MOVIE, $event)"
      />
    </div>

    <!-- Empty state -->
    <div v-else-if="query && !loading" class="text-center py-20 text-gray-500">
      <p class="text-lg">No results for "{{ query }}"</p>
    </div>

    <!-- Default state -->
    <div v-else-if="!query">
      <h2 class="section-title mb-4">Trending Right Now</h2>
      <div v-if="loadingDefault" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <div v-for="n in 10" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
      </div>
      <div v-else class="space-y-8">
        <div v-if="trendingMovies.length">
          <h3 class="section-title mb-4">Movies</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <MediaCard
              v-for="item in trendingMovies"
              :key="`movie-${item.id}`"
              :item="item"
              :media-type="MEDIA_TYPE.MOVIE"
              :watched="isWatchedStatus(item)"
              :status="item.user_status?.status || 'none'"
              :show-quick-action="auth.isAuthenticated && canToggleWatchlist(item)"
              :quick-action-active="item.user_status?.status === 'plan_to_watch'"
              :quick-action-loading="isLoading(MEDIA_TYPE.MOVIE, item.id)"
              :quick-action-pulsing="isPulsing(MEDIA_TYPE.MOVIE, item.id)"
              :quick-action-aria-label="getWatchlistAriaLabel(MEDIA_TYPE.MOVIE, item.user_status?.status === 'plan_to_watch')"
              :show-watched-quick-action="auth.isAuthenticated"
              :watched-quick-action-loading="isWatchedLoading(MEDIA_TYPE.MOVIE, item.id)"
              :watched-quick-action-pulsing="isWatchedPulsing(MEDIA_TYPE.MOVIE, item.id)"
              :watched-quick-action-aria-label="t('tracking_mark_as_watched')"
              @quick-action-watchlist="handleQuickAction(item, MEDIA_TYPE.MOVIE)"
              @quick-action-watch-option="handleWatchOption(item, MEDIA_TYPE.MOVIE, $event)"
            />
          </div>
        </div>

        <div v-if="trendingTvShows.length">
          <h3 class="section-title mb-4">TV Shows</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <MediaCard
              v-for="item in trendingTvShows"
              :key="`tv-${item.id}`"
              :item="item"
              :media-type="MEDIA_TYPE.TV"
              :watched="isWatchedStatus(item)"
              :status="item.user_status?.status || 'none'"
              :show-quick-action="auth.isAuthenticated && canToggleWatchlist(item)"
              :quick-action-active="item.user_status?.status === 'plan_to_watch'"
              :quick-action-loading="isLoading(MEDIA_TYPE.TV, item.id)"
              :quick-action-pulsing="isPulsing(MEDIA_TYPE.TV, item.id)"
              :quick-action-aria-label="getWatchlistAriaLabel(MEDIA_TYPE.TV, item.user_status?.status === 'plan_to_watch')"
              :show-watched-quick-action="auth.isAuthenticated"
              :watched-quick-action-loading="isWatchedLoading(MEDIA_TYPE.TV, item.id)"
              :watched-quick-action-pulsing="isWatchedPulsing(MEDIA_TYPE.TV, item.id)"
              :watched-quick-action-aria-label="t('tracking_mark_as_watched')"
              @quick-action-watchlist="handleQuickAction(item, MEDIA_TYPE.TV)"
              @quick-action-watch-option="handleWatchOption(item, MEDIA_TYPE.TV, $event)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { mediaAPI } from '@/api'
import MediaCard from '@/components/MediaCard.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import { useAuthStore } from '@/stores/auth'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useWatchlistQuickActions } from '@/composables/useWatchlistQuickActions'
import { useWatchedQuickActions } from '@/composables/useWatchedQuickActions'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'
import { useI18n } from '@/i18n'

const route = useRoute()
const query = ref(route.query.q || '')
const results = ref([])
const trendingMovies = ref([])
const trendingTvShows = ref([])
const loading = ref(false)
const loadingDefault = ref(true)
const activeFilter = ref('multi')
const quickActionError = ref('')
const auth = useAuthStore()
const { t } = useI18n()

const {
  showDatePicker,
  pickerInitialValue,
  pickWatchedDateTime,
  handleDatePickerConfirm,
  handleDatePickerCancel,
} = useWatchedDateTimePicker()

const { resetTransientState, isLoading, isPulsing, toggleWatchlist } = useWatchlistQuickActions()
const {
  resetTransientState: resetWatchedTransientState,
  isLoading: isWatchedLoading,
  isPulsing: isWatchedPulsing,
  markWatched,
} = useWatchedQuickActions()

function canToggleWatchlist(item) {
  const status = item?.user_status?.status
  return status !== WATCH_ENTRY_STATUS.WATCHED && status !== WATCH_ENTRY_STATUS.WATCHING
}

function isWatchedStatus(item) {
  const status = item?.user_status?.status
  return status === WATCH_ENTRY_STATUS.WATCHED || status === WATCH_ENTRY_STATUS.WATCHING
}

const filters = [
  { label: 'All', value: 'multi' },
  { label: 'Movies', value: MEDIA_TYPE.MOVIE },
  { label: 'TV Shows', value: MEDIA_TYPE.TV },
]

let debounceTimer = null
function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(doSearch, 400)
}

async function doSearch() {
  if (!query.value.trim()) {
    results.value = []
    return
  }
  loading.value = true
  try {
    const data = await mediaAPI.search(query.value, activeFilter.value)
    if (data) {
      const type = activeFilter.value
      results.value = (data.results || []).map(r => ({
        ...r,
        media_type: (type === 'multi') ? (r.media_type || MEDIA_TYPE.MOVIE) : type
      }))
    }
  } finally {
    loading.value = false
  }
}

function showQuickActionError(message) {
  quickActionError.value = message
  setTimeout(() => {
    quickActionError.value = ''
  }, 3500)
}

async function handleQuickAction(item, mediaType) {
  try {
    if (!canToggleWatchlist(item)) {
      return
    }
    const inWatchlist = item?.user_status?.status === 'plan_to_watch'
    const result = await toggleWatchlist(mediaType, item.id, inWatchlist)
    item.user_status = {
      ...(item.user_status || {}),
      status: result === 'removed' ? 'none' : 'plan_to_watch',
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

    const nextStatus = await markWatched(mediaType, item.id, watchedAt)
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

function getWatchlistAriaLabel(mediaType, inWatchlist) {
  if (mediaType === MEDIA_TYPE.TV) {
    return inWatchlist ? t('watchlist_remove_show') : t('watchlist_add_show')
  }
  return inWatchlist ? t('watchlist_remove_movie') : t('watchlist_add_movie')
}

onMounted(async () => {
  if (query.value) doSearch()
  try {
    const [moviesData, tvData] = await Promise.all([
      mediaAPI.trending(MEDIA_TYPE.MOVIE),
      mediaAPI.trending(MEDIA_TYPE.TV),
    ])
    trendingMovies.value = moviesData?.results?.slice(0, 10) || []
    trendingTvShows.value = tvData?.results?.slice(0, 10) || []
  } finally {
    loadingDefault.value = false
  }
})

watch(
  () => auth.isAuthenticated,
  async (isAuthenticated) => {
    if (!isAuthenticated) {
      resetTransientState()
      resetWatchedTransientState()
      return
    }
  },
  { immediate: true }
)
</script>
