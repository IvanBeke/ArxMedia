<template>
  <div class="overflow-x-hidden">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this movie?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <MovieUnwatchDialog ref="unwatchDialog" :on-error="showError" @unwatched="onMovieUnwatched" />

    <DetailHero
      :backdrop-url="movie?.backdrop_url"
      :backdrop-alt="movie?.title"
      :poster-url="movie?.poster_url"
      :poster-alt="movie?.title"
      :loading="loading"
    >
      <template #eyebrow>
        <div v-if="movie" class="flex flex-wrap gap-2 mb-3">
          <span v-for="g in movie.genres" :key="g.id" class="badge bg-surface-200 text-secondary text-xs">{{ g.name }}</span>
        </div>
      </template>
      <template #title>
        <h1 v-if="movie" class="font-display text-3xl md:text-5xl text-primary font-semibold mb-1 break-words">{{ movie.title }}</h1>
      </template>
      <template #meta>
        <template v-if="movie">
          <p v-if="movie.tagline" class="text-gray-500 italic text-sm mb-2 break-words">{{ movie.tagline }}</p>
          <p class="text-gray-500 text-sm mb-1">
            {{ releaseYear(movie.release_date) }}
            <span v-if="runtimeLabel"> · {{ runtimeLabel }}</span>
            <span v-if="movie.status"> · {{ movie.status }}</span>
          </p>
          <p class="text-gray-600 text-xs mb-3">{{ formatDateByLocale(movie.release_date) }}</p>
          <div class="flex items-center gap-4 mb-1 text-sm">
            <RatingBadge :value="movie.vote_average ?? 0" :votes="movie.vote_count" out-of-ten />
          </div>
        </template>
      </template>
      <template #description>
        <SpoilerBlock v-if="movie" :item-key="`movie-overview-${route.params.id}`" :watched="watchedCount > 0" class="mt-4 mb-4 max-w-2xl">
          <p class="text-secondary leading-relaxed break-words">{{ movie.overview }}</p>
        </SpoilerBlock>
      </template>
      <template #links>
        <ExternalLinks
          v-if="movie"
          :tmdb-url="externalLinks.tmdbUrl"
          :tvmaze-url="externalLinks.tvmazeUrl"
          :imdb-url="externalLinks.imdbUrl"
          class="mb-4"
        />
      </template>
      <template #actions>
        <MediaActionsBar v-if="movie && auth.isAuthenticated">
          <WatchSplitButton
            :active="watchedCount > 0 && !isDropped"
            :variant="isDropped ? 'danger' : 'default'"
            :label="watchedMessage"
            :release-date="movie?.release_date ?? ''"
            :title-text="watchedTooltip"
            @trigger="handleWatchTrigger"
            @select="handleWatchOption"
          >
            <template #menuFooter>
              <div v-if="!isDropped">
                <button
                  type="button"
                  @click="handleDropMovie"
                  class="block w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-surface-200 hover:text-red-300 transition-colors rounded"
                >
                  Drop movie
                </button>
              </div>
            </template>
          </WatchSplitButton>
          <ActionGhostButton v-if="watchedCount === 0" :active="inWatchlist" @click="toggleWatchlist">
            <template #icon>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
              </svg>
            </template>
            {{ inWatchlist ? 'In Watchlist' : 'Watchlist' }}
          </ActionGhostButton>
          <AddToListPopover
            :media-type="MEDIA_TYPE.MOVIE"
            :tmdb-id="Number(route.params.id)"
            @added="() => showSuccess('Added to list')"
          />
          <template #rating>
            <StarRating v-if="canRate" v-model="userRating" @update:modelValue="submitRating" />
            <p v-else class="text-xs text-muted">{{ t('rating_movie_requires_watched') }}</p>
          </template>
          <template #messages>
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
        </MediaActionsBar>
      </template>
    </DetailHero>

    <div v-if="!loading && movie" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
      <MediaTabs v-model="activeTab" :tabs="visibleTabs" aria-label="Movie sections" />

      <div class="mt-6" role="tabpanel" :id="`tabpanel-${activeTab}`" :aria-labelledby="`tab-${activeTab}`">
        <template v-if="activeTab === 'overview'">
          <div class="grid md:grid-cols-3 gap-8">
            <div class="md:col-span-2 space-y-6 min-w-0">
              <div v-if="movie.watch_providers" class="min-w-0">
                <p class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Watch Now (Powered by JustWatch)</p>
                <div class="flex flex-wrap gap-2">
                  <div
                    v-for="p in (movie.watch_providers.flatrate || []).slice(0, 6)"
                    :key="`provider-${p.provider_id}`"
                    class="inline-flex items-center gap-2 rounded-lg border border-surface-200 bg-surface-100/70 px-2.5 py-2 text-sm text-secondary max-w-full"
                  >
                    <img v-if="p.logo_path" :src="tmdbImageUrl(p.logo_path, 'w92') || ''" :alt="`${p.provider_name} logo`" class="h-10 w-10 rounded-md object-cover shrink-0" loading="lazy" decoding="async" />
                    <span class="truncate">{{ p.provider_name }}</span>
                  </div>
                  <span v-if="!(movie.watch_providers.flatrate || []).length" class="text-xs text-muted">No streaming providers found.</span>
                </div>
              </div>
              <div v-if="topCrew.length" class="min-w-0">
                <p class="text-gray-500 text-xs mb-2">Crew highlights</p>
                <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <div v-for="person in topCrew" :key="person.credit_id" class="text-gray-400 max-w-full break-words">
                    <span class="text-gray-500">{{ person.job }}:</span> {{ person.name }}
                  </div>
                </div>
              </div>
            </div>
            <div class="space-y-4 min-w-0">
              <div class="card p-4">
                <p class="text-xs text-gray-500 uppercase tracking-wider mb-2">Details</p>
                <dl class="text-sm space-y-1.5">
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">Status</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ movie.status || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">Runtime</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ runtimeLabel || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">Released</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ formatDateByLocale(movie.release_date) || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">Language</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ movie.language || '—' }}</dd>
                  </div>
                </dl>
              </div>
              <div class="card p-4 space-y-2">
                <button
                  v-if="auth.isAuthenticated"
                  type="button"
                  @click="refreshMetadata"
                  :disabled="refreshingMetadata"
                  class="btn-ghost text-xs border border-surface-200 bg-surface-100/70 hover:bg-surface-100 w-full"
                >
                  {{ refreshingMetadata ? 'Updating metadata...' : 'Update metadata from TMDB and TVMaze' }}
                </button>
                <p class="text-xs text-muted break-words">
                  Last metadata update: {{ metadataUpdatedAtLabel }}
                </p>
              </div>
            </div>
          </div>

          <div class="mt-8">
            <h3 class="text-primary font-medium mb-3">Top cast</h3>
            <CastGrid :people="(creditsData?.cast || []).slice(0, 8)" />
            <button v-if="(creditsData?.cast || []).length > 8" type="button" class="mt-3 text-sm text-brand-400 hover:text-brand-300" @click="setTab('cast')">
              View all cast →
            </button>
          </div>
        </template>

        <template v-else-if="activeTab === 'cast'">
          <h3 class="text-primary font-medium mb-3">Cast{{ creditsData?.cast?.length ? ` (${creditsData.cast.length})` : '' }}</h3>
          <CastGrid :people="creditsData?.cast || []" />
          <div v-if="(creditsData?.crew || []).length" class="mt-8">
            <h3 class="text-primary font-medium mb-3">Crew</h3>
            <CastGrid :people="creditsData?.crew || []" empty-label="No crew information available." />
          </div>
        </template>

        <template v-else-if="activeTab === 'collection'">
          <CollectionStrip :collection="collectionDetail" :loading="loadingCollection" />
        </template>

        <template v-else-if="activeTab === 'history'">
          <MediaHistoryTab :filter="historyFilter" />
        </template>

        <template v-else-if="activeTab === 'more'">
          <p v-if="recsError" class="text-sm text-muted mb-3">Recommendations unavailable right now.</p>
          <RecommendationsRow :items="recommendations" :loading="loadingRecs" @status-changed="handleRecommendationStatusChanged" />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mediaAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import StarRating from '@/components/StarRating.vue'
import WatchSplitButton from '@/components/WatchSplitButton.vue'
import ActionGhostButton from '@/components/ActionGhostButton.vue'
import AddToListPopover from '@/components/AddToListPopover.vue'
import SpoilerBlock from '@/components/SpoilerBlock.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import MovieUnwatchDialog from '@/components/MovieUnwatchDialog.vue'
import DetailHero from '@/components/DetailHero.vue'
import MediaTabs, { type MediaTab } from '@/components/MediaTabs.vue'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import MediaActionsBar from '@/components/MediaActionsBar.vue'
import ExternalLinks from '@/components/ExternalLinks.vue'
import CastGrid from '@/components/CastGrid.vue'
import RecommendationsRow from '@/components/RecommendationsRow.vue'
import CollectionStrip from '@/components/CollectionStrip.vue'
import { MEDIA_TYPE, WATCH_ENTRY_MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { formatDateByLocale, useI18n } from '@/i18n'
import { getApiErrorMessage } from '@/utils/errors'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { tmdbImageUrl } from '@/utils/images'
import { applyStatusChanged, type MediaStatusChangedPayload } from '@/utils/mediaStatusSync'
import { canRateByStatus, formatUpdatedAtLabel } from '@/utils/mediaStatus'
import { formatHoursMinutes } from '@/utils/progress'
import { movieExternalLinks } from '@/utils/externalLinks'
import { instantEpochMs, instantFromEpochMs, nowInstantIso, temporalYear } from '@/utils/temporal'
import { watchedTooltipText } from '@/utils/watchOptions'
import type { CollectionDetail, Credits, MediaResult, Movie, PaginatedResponse, WatchEntry } from '@/types/api'
import type { WatchedAtOption } from '@/utils/watchOptions'

const route = useRoute()
const router = useRouter()
const movieId = computed(() => String(route.params.id ?? ''))
const historyFilter = computed(() => ({
  media_type: WATCH_ENTRY_MEDIA_TYPE.MOVIE,
  tmdb_id: movieId.value,
}))
const auth = useAuthStore()
const { t } = useI18n()
const movie = ref<Movie | null>(null)
const creditsData = ref<Credits | null>(null)
const collectionDetail = ref<CollectionDetail | null>(null)
const recommendations = ref<MediaResult[]>([])
const loading = ref(true)
const loadingCollection = ref(false)
const loadingRecs = ref(false)
const recsError = ref(false)
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
const unwatchDialog = ref<InstanceType<typeof MovieUnwatchDialog> | null>(null)
const refreshingMetadata = ref(false)

const {
  showDatePicker,
  pickerInitialValue,
  handleQuickAction: runQuickAction,
  handleWatchOption: runWatchOption,
  handleDatePickerConfirm,
  handleDatePickerCancel,
} = useMediaCardQuickActions({ onError: showError })

const watchedMessage = computed(() => {
  if (isDropped.value) return 'Dropped'
  return watchedCount.value > 0 ? 'Watched' : 'Watch'
})

const isDropped = computed(() => movie.value?.user_status?.status === WATCH_ENTRY_STATUS.DROPPED)

const watchedTooltip = computed(() => watchedTooltipText(watchedCount.value > 0, latestWatchedAt.value, t))

const metadataUpdatedAtLabel = computed(() => formatUpdatedAtLabel(movie.value?.metadata_updated_at))

const externalLinks = computed(() => movieExternalLinks(movieId.value, movie.value?.external_ids))

const runtimeLabel = computed(() => {
  const runtime = Number(movie.value?.runtime)
  if (!Number.isFinite(runtime) || runtime <= 0) {
    return ''
  }
  return formatHoursMinutes(runtime)
})

const canRate = computed(() => canRateByStatus(movie.value?.user_status?.status))

const topCrew = computed(() => {
  const crew = creditsData.value?.crew || []
  const priority = ['Director', 'Writer', 'Screenplay', 'Novel', 'Producer']
  return crew
    .filter((p) => priority.includes(p.job || ''))
    .sort((a, b) => priority.indexOf(a.job || '') - priority.indexOf(b.job || ''))
    .slice(0, 6)
})

const VALID_TABS = ['overview', 'cast', 'collection', 'history', 'more'] as const
type MovieTab = (typeof VALID_TABS)[number]

function initialTab(): MovieTab {
  const raw = String(route.query.tab || 'overview')
  return (VALID_TABS as readonly string[]).includes(raw) ? (raw as MovieTab) : 'overview'
}

const activeTab = ref<MovieTab>(initialTab())

const visibleTabs = computed((): MediaTab[] => {
  const tabs: MediaTab[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'cast', label: 'Cast', count: creditsData.value?.cast?.length },
    { id: 'history', label: 'History' },
  ]
  if (movie.value?.collection?.id) {
    tabs.push({ id: 'collection', label: 'Collection' })
  }
  if (recommendations.value.length > 0 || loadingRecs.value) {
    tabs.push({ id: 'more', label: 'More like this' })
  } else if (!loadingRecs.value && !recsError.value && recommendations.value.length === 0) {
    // hidden when empty — no tab
  } else if (recsError.value) {
    // hidden on error — notice shown in overview? keep hidden per plan
  }
  if (!tabs.some((tab) => tab.id === activeTab.value)) {
    activeTab.value = 'overview'
  }
  return tabs
})

function setTab(tab: MovieTab) {
  activeTab.value = tab
}

watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

watch(() => route.query.tab, (raw) => {
  const value = String(raw || 'overview')
  if ((VALID_TABS as readonly string[]).includes(value) && value !== activeTab.value) {
    const allowed = visibleTabs.value.some((tab) => tab.id === value)
    activeTab.value = (allowed ? value : 'overview') as MovieTab
  }
})

function releaseYear(value: string | null | undefined) {
  if (!value) return ''
  return temporalYear(value) || ''
}

function applyWatchHistory(response: PaginatedResponse<WatchEntry> | WatchEntry[]) {
  const entries = Array.isArray(response) ? response : response.results
  watchedCount.value = entries.length
  const watchedDates = entries
    .map((entry) => entry.watched_at)
    .filter(Boolean)
    .map((value) => instantEpochMs(value))
    .filter((value) => Number.isFinite(value))
  if (watchedDates.length) {
    latestWatchedAt.value = instantFromEpochMs(Math.max(...watchedDates))
  } else {
    latestWatchedAt.value = ''
  }
}

async function refreshWatchHistory() {
  try {
    const response = await trackingAPI.getHistory({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: movieId.value })
    applyWatchHistory(response)
  } catch (e) {
    console.error('Failed to load watch history:', e)
  }
}

function openUnwatchConfirm() {
  if (movie.value) {
    unwatchDialog.value?.open(movie.value)
  }
}

async function onMovieUnwatched() {
  await refreshWatchHistory()
  inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
  showSuccess('Removed from watched history')
}

async function loadCollection() {
  const collectionId = movie.value?.collection?.id
  if (!collectionId) return
  loadingCollection.value = true
  try {
    collectionDetail.value = await mediaAPI.getCollection(collectionId)
  } catch (e) {
    console.error('Failed to load collection:', e)
  } finally {
    loadingCollection.value = false
  }
}

async function loadRecommendations() {
  loadingRecs.value = true
  recsError.value = false
  try {
    const data = await mediaAPI.getMovieRecommendations(movieId.value)
    recommendations.value = (data.results || []).map((item) => ({ ...item, media_type: MEDIA_TYPE.MOVIE }))
  } catch (e) {
    console.error('Failed to load recommendations:', e)
    recsError.value = true
  } finally {
    loadingRecs.value = false
  }
}

function handleRecommendationStatusChanged(payload: MediaStatusChangedPayload) {
  applyStatusChanged(recommendations.value, payload)
}

onMounted(async () => {
  try {
    const [movieRes, creditsRes] = await Promise.all([
      mediaAPI.getMovie(movieId.value),
      mediaAPI.getMovieCredits(movieId.value).catch(() => null),
    ])
    movie.value = movieRes
    creditsData.value = creditsRes
    void loadCollection()
    void loadRecommendations()
  } finally {
    loading.value = false
  }

  if (auth.isAuthenticated) {
    const [histRes, ratingRes] = await Promise.allSettled([
      trackingAPI.getHistory({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: movieId.value }),
      trackingAPI.getRatings({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: movieId.value })
    ])
    if (histRes.status === 'fulfilled') {
      applyWatchHistory(histRes.value)
    }
    inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
    if (ratingRes.status === 'fulfilled') {
      const ratings = Array.isArray(ratingRes.value) ? ratingRes.value : ratingRes.value.results
      const found = ratings[0]
      if (found) userRating.value = found.score
    }
  }
})

async function handleWatchTrigger() {
  if (watchedCount.value > 0) {
    openUnwatchConfirm()
    return
  }
  await handleWatchOption('now')
}

async function handleWatchOption(option: WatchedAtOption) {
  if (!movie.value) {
    return
  }

  if (option === 'date') {
    movie.value.user_status = {
      status: movie.value.user_status?.status ?? WATCH_ENTRY_STATUS.NONE,
      ...movie.value.user_status,
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

async function handleDropMovie() {
  if (!movie.value) {
    return
  }
  try {
    await trackingAPI.dropMedia({ tmdb_id: movieId.value, media_type: MEDIA_TYPE.MOVIE })
    movie.value = await mediaAPI.getMovie(movieId.value)
    inWatchlist.value = false
    showSuccess('Movie dropped')
  } catch (error) {
    showError(getApiErrorMessage(error, 'Could not drop movie.'))
  }
}

async function toggleWatchlist() {  if (!movie.value) {
    return
  }

  const result = await runQuickAction(movie.value, MEDIA_TYPE.MOVIE)
  if (!result) {
    return
  }

  inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
  showSuccess(result === 'removed' ? 'Removed from watchlist' : 'Added to watchlist!')
}

async function submitRating(score: number) {
  try {
    await trackingAPI.rate({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: movieId.value, score })
    showSuccess(`Rated ${score}/10!`)
  } catch (error) {
    showError(getApiErrorMessage(error, t('rating_movie_requires_watched')))
  }
}

async function refreshMetadata() {
  if (refreshingMetadata.value) return
  refreshingMetadata.value = true
  try {
    await mediaAPI.refreshMovie(movieId.value)
    movie.value = await mediaAPI.getMovie(movieId.value)
    inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
    showMetadataSuccess('Metadata updated from TMDB and TVMaze')
  } catch (error) {
    showMetadataError(getApiErrorMessage(error, 'Could not refresh metadata.'))
  } finally {
    refreshingMetadata.value = false
  }
}
</script>
