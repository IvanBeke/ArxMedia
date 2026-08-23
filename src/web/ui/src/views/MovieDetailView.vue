<template>
  <div>
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this movie?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <MovieUnwatchDialog ref="unwatchDialog" :on-error="showError" @unwatched="onMovieUnwatched" />

    <!-- Backdrop -->
    <div class="relative h-72 md:h-[28rem]">
      <img v-if="movie?.backdrop_url" :src="movie.backdrop_url" class="w-full h-full object-cover" :alt="movie?.title" />
      <div class="absolute inset-0 bg-gradient-to-t from-surface via-surface/60 to-transparent"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-surface/80 to-transparent"></div>
    </div>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-60 md:-mt-96 relative z-10 pb-20">
      <div class="flex flex-col md:flex-row gap-8">
        <!-- Poster -->
        <div class="flex-shrink-0">
          <div class="w-36 md:w-48 rounded-md overflow-hidden shadow-2xl border border-surface-200">
            <img v-if="movie?.poster_url" :src="movie.poster_url" :alt="movie?.title" class="w-full" />
            <div v-else class="aspect-[2/3] bg-gradient-to-br from-surface-200 to-surface-100 flex flex-col items-center justify-center text-gray-500 p-4">
              <svg class="w-12 h-12 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M15 10l4.553-2.069A1 1 0 0121 8.876V15.5a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z"/>
              </svg>
              <span class="text-xs text-center">{{ movie?.title }}</span>
            </div>
          </div>
        </div>

        <!-- Info -->
        <div class="flex-1 pt-2">
          <div v-if="loading" class="space-y-3">
            <div class="h-10 w-3/4 skeleton rounded-md"></div>
            <div class="h-4 w-1/2 skeleton rounded-md"></div>
            <div class="h-20 skeleton rounded-md"></div>
          </div>

          <template v-else-if="movie">
            <div class="flex flex-wrap gap-2 mb-3">
              <span v-for="g in movie.genres" :key="g.id" class="badge bg-surface-200 text-secondary text-xs">{{ g.name }}</span>
            </div>

            <h1 class="font-display text-3xl md:text-5xl text-primary font-semibold mb-1">{{ movie.title }}</h1>
            <p v-if="movie.tagline" class="text-gray-500 italic text-sm mb-3">{{ movie.tagline }}</p>
            <p class="text-gray-500 text-sm mb-4">
              {{ releaseYear(movie.release_date) }}
              <span v-if="runtimeLabel"> · {{ runtimeLabel }}</span>
            </p>
            <p class="text-gray-600 text-xs mb-4">{{ formatDateByLocale(movie.release_date) }}</p>

            <div class="flex items-center gap-4 mb-4 text-sm">
              <RatingBadge :value="movie.vote_average" :votes="movie.vote_count" out-of-ten />
            </div>

            <Transition name="fade">
              <div v-if="metadataSuccessMsg" class="mb-3 px-3 py-1.5 bg-green-500/10 border border-green-500/20 text-green-400 rounded-md text-sm inline-block">
                {{ metadataSuccessMsg }}
              </div>
            </Transition>
            <Transition name="fade">
              <div v-if="metadataErrorMsg" class="mb-3 px-3 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm inline-block">
                {{ metadataErrorMsg }}
              </div>
            </Transition>

            <div class="mb-3 flex flex-wrap items-center gap-3">
              <button
                v-if="auth.isAuthenticated"
                type="button"
                @click="refreshMetadata"
                :disabled="refreshingMetadata"
                class="btn-ghost text-xs border border-surface-200 bg-surface-100/70 hover:bg-surface-100"
              >
                {{ refreshingMetadata ? 'Updating metadata...' : 'Update metadata from TMDB' }}
              </button>
              <span class="text-xs text-muted">
                Last metadata update: {{ metadataUpdatedAtLabel }}
              </span>
            </div>

            <SpoilerBlock :item-key="`movie-overview-${route.params.id}`" :watched="watchedCount > 0" class="mb-6 max-w-2xl">
              <p class="text-secondary leading-relaxed">{{ movie.overview }}</p>
            </SpoilerBlock>

            <div v-if="movie.watch_providers" class="mb-6">
              <p class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Watch Now (Powered by JustWatch)</p>
              <div class="flex flex-wrap gap-2">
                <div
                  v-for="p in (movie.watch_providers.flatrate || []).slice(0, 6)"
                  :key="`provider-${p.provider_id}`"
                  class="inline-flex items-center gap-2 rounded-lg border border-surface-200 bg-surface-100/70 px-2.5 py-2 text-sm text-secondary"
                >
                  <img v-if="p.logo_path" :src="tmdbImageUrl(p.logo_path, 'w92')" :alt="`${p.provider_name} logo`" class="h-10 w-10 rounded-md object-cover shrink-0" loading="lazy" decoding="async" />
                  {{ p.provider_name }}
                </div>
                <span v-if="!(movie.watch_providers.flatrate || []).length" class="text-xs text-muted">No streaming providers found.</span>
              </div>
            </div>

            <div v-if="creditsData?.crew?.length" class="mb-4">
              <p class="text-gray-500 text-xs mb-2">Crew</p>
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                <div v-for="person in creditsData.crew.slice(0, 8)" :key="person.credit_id" class="text-gray-400">
                  <span class="text-gray-500">{{ person.job }}:</span> {{ person.name }}
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div v-if="auth.isAuthenticated" class="flex flex-wrap gap-2 mb-4">
              <button
                v-if="watchedCount > 0"
                type="button"
                class="cursor-pointer p-1 rounded hover:bg-surface-200 text-muted hover:text-brand-400 border-none bg-transparent transition-colors"
                :title="watchedTooltip"
                @click="openUnwatchConfirm"
              >
                <div class="flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  {{ watchedMessage }}
                </div>
              </button>
              <WatchMenu
                v-else
                :release-date="movie?.release_date"
                :button-title="watchedTooltip"
                @select="handleWatchOption"
              >
                <div class="flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  {{ watchedMessage }}
                </div>
              </WatchMenu>
              <button v-if="watchedCount === 0" @click="toggleWatchlist" class="btn-ghost flex items-center gap-2 text-sm">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                </svg>
                {{ inWatchlist ? 'In Watchlist' : 'Watchlist' }}
              </button>
              <AddToListPopover
                :media-type="MEDIA_TYPE.MOVIE"
                :tmdb-id="Number(route.params.id)"
                @added="() => showSuccess('Added to list')"
              />
            </div>

            <div v-if="auth.isAuthenticated" class="mb-4">
              <p class="text-xs text-gray-500 mb-1.5 uppercase tracking-wider">Your Rating</p>
              <StarRating v-if="canRate" v-model="userRating" @update:modelValue="submitRating" />
              <p v-else class="text-xs text-muted">{{ t('rating_movie_requires_watched') }}</p>
            </div>

            <Transition name="fade">
              <div v-if="successMsg" class="mb-4 px-3 py-1.5 bg-green-500/10 border border-green-500/20 text-green-400 rounded-md text-sm inline-block">
                {{ successMsg }}
              </div>
            </Transition>
            <Transition name="fade">
              <div v-if="errorMsg" class="mb-4 px-3 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm inline-block">
                {{ errorMsg }}
              </div>
            </Transition>
          </template>
        </div>
      </div>

      <div v-if="creditsData?.cast?.length" class="mt-8">
        <p class="text-gray-500 text-xs mb-2">Cast</p>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 text-sm">
          <div v-for="actor in creditsData.cast" :key="actor.credit_id" class="flex items-center gap-3">
            <img v-if="actor.profile_path" :src="tmdbImageUrl(actor.profile_path, 'w92')" :alt="actor.name" class="w-12 h-12 rounded-md object-cover" />
            <div v-else class="w-12 h-12 rounded-md bg-surface-200"></div>
            <div class="min-w-0">
              <p class="text-secondary">{{ actor.name }}</p>
              <p class="text-gray-500">{{ actor.character }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { mediaAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import StarRating from '@/components/StarRating.vue'
import WatchMenu from '@/components/WatchMenu.vue'
import AddToListPopover from '@/components/AddToListPopover.vue'
import SpoilerBlock from '@/components/SpoilerBlock.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import MovieUnwatchDialog from '@/components/MovieUnwatchDialog.vue'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { formatDateByLocale, useI18n } from '@/i18n'
import { getApiErrorMessage } from '@/utils/errors'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { tmdbImageUrl } from '@/utils/images'
import { canRateByStatus, formatUpdatedAtLabel } from '@/utils/mediaStatus'
import { formatHoursMinutes } from '@/utils/progress'
import { instantEpochMs, instantFromEpochMs, nowInstantIso, temporalYear } from '@/utils/temporal'
import { watchedTooltipText } from '@/utils/watchOptions'

const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()
const movie = ref(null)
const creditsData = ref(null)
const loading = ref(true)
const userRating = ref(0)
const watchedCount = ref(0)
const latestWatchedAt = ref('')
const inWatchlist = ref(false)
const metadataFlash = useFlashMessages()
const {
  successMsg: metadataSuccessMsg,
  errorMsg: metadataErrorMsg,
  showSuccess: showMetadataSuccess,
  showError: showMetadataError,
} = metadataFlash
const { successMsg, errorMsg, showSuccess, showError } = useFlashMessages()
const unwatchDialog = ref(null)
const refreshingMetadata = ref(false)

const {
  showDatePicker,
  pickerInitialValue,
  handleQuickAction: runQuickAction,
  handleWatchOption: runWatchOption,
  handleDatePickerConfirm,
  handleDatePickerCancel,
} = useMediaCardQuickActions({ onError: showError })

const watchedMessage = computed(() => watchedCount.value > 0 ? `Watched (${watchedCount.value}×)` : 'Mark as Watched')

const watchedTooltip = computed(() => watchedTooltipText(watchedCount.value > 0, latestWatchedAt.value, t))

const metadataUpdatedAtLabel = computed(() => formatUpdatedAtLabel(movie.value?.metadata_updated_at))

const runtimeLabel = computed(() => {
  const runtime = Number(movie.value?.runtime)
  if (!Number.isFinite(runtime) || runtime <= 0) {
    return ''
  }
  return formatHoursMinutes(runtime)
})

const canRate = computed(() => canRateByStatus(movie.value?.user_status?.status))

function releaseYear(value) {
  if (!value) return ''
  return temporalYear(value) || ''
}

function applyWatchHistory(response) {
  const entries = response?.results || response || []
  watchedCount.value = entries.length
  const watchedDates = entries
    .map(e => e.watched_at)
    .filter(Boolean)
    .map(v => instantEpochMs(v))
    .filter(v => Number.isFinite(v))
  if (watchedDates.length) {
    latestWatchedAt.value = instantFromEpochMs(Math.max(...watchedDates))
  } else {
    latestWatchedAt.value = ''
  }
}

async function refreshWatchHistory() {
  try {
    const response = await trackingAPI.getHistory({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: route.params.id })
    applyWatchHistory(response)
  } catch (e) {
    console.error('Failed to load watch history:', e)
  }
}

function openUnwatchConfirm() {
  unwatchDialog.value?.open(movie.value)
}

async function onMovieUnwatched() {
  await refreshWatchHistory()
  inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
  showSuccess('Removed from watched history')
}

onMounted(async () => {
  try {
    const [movieRes, creditsRes] = await Promise.all([
      mediaAPI.getMovie(route.params.id),
      mediaAPI.getMovieCredits(route.params.id)
    ])
    movie.value = movieRes
    creditsData.value = creditsRes
  } finally {
    loading.value = false
  }

  if (auth.isAuthenticated) {
    const [histRes, ratingRes] = await Promise.allSettled([
      trackingAPI.getHistory({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: route.params.id }),
      trackingAPI.getRatings({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: route.params.id })
    ])
    if (histRes.status === 'fulfilled') {
      applyWatchHistory(histRes.value)
    }
    inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
    if (ratingRes.status === 'fulfilled') {
      const ratings = ratingRes.value.results || ratingRes.value
      const found = ratings[0]
      if (found) userRating.value = found.score
    }
  }
})

async function handleWatchOption(option) {
  if (!movie.value) {
    return
  }

  if (option === 'date') {
    movie.value.user_status = {
      ...(movie.value.user_status || {}),
      watched_at: latestWatchedAt.value,
    }
  }

  const nextStatus = await runWatchOption(movie.value, MEDIA_TYPE.MOVIE, option)
  if (!nextStatus) {
    return
  }

  watchedCount.value++
  inWatchlist.value = false
  latestWatchedAt.value = movie.value?.user_status?.watched_at || nowInstantIso()
  showSuccess('Marked as watched!')
}

async function toggleWatchlist() {
  if (!movie.value) {
    return
  }

  const result = await runQuickAction(movie.value, MEDIA_TYPE.MOVIE)
  if (!result) {
    return
  }

  inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
  showSuccess(result === 'removed' ? 'Removed from watchlist' : 'Added to watchlist!')
}

async function submitRating(score) {
  try {
    await trackingAPI.rate({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: route.params.id, score })
    showSuccess(`Rated ${score}/10!`)
  } catch (error) {
    showError(getApiErrorMessage(error, t('rating_movie_requires_watched')))
  }
}

async function refreshMetadata() {
  if (refreshingMetadata.value) return
  refreshingMetadata.value = true
  try {
    await mediaAPI.refreshMovie(route.params.id)
    movie.value = await mediaAPI.getMovie(route.params.id)
    inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
    showMetadataSuccess('Metadata updated from TMDB')
  } catch (error) {
    showMetadataError(getApiErrorMessage(error, 'Could not refresh metadata.'))
  } finally {
    refreshingMetadata.value = false
  }
}
</script>
