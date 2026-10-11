<template>
  <div class="overflow-x-hidden">
    <FlashToast
      :messages="[
        { text: metadataSuccessMsg, kind: 'success' },
        { text: metadataErrorMsg, kind: 'error' },
        { text: successMsg, kind: 'success' },
        { text: errorMsg, kind: 'error' },
      ]"
    />
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      :title="t('picker_when_movie')"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <MovieUnwatchDialog ref="unwatchDialog" :on-error="showError" @unwatched="onMovieUnwatched" />

    <div v-if="loadError" class="max-w-3xl mx-auto px-4 py-16">
      <LoadError :message="loadError" @retry="loadPage" />
    </div>

    <DetailHero
      v-else
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
                  {{ t('movie_drop') }}
                </button>
              </div>
            </template>
          </WatchSplitButton>
          <ActionGhostButton v-if="watchedCount === 0" :active="inWatchlist" :title="watchlistTitle" @click="toggleWatchlist">
            <template #icon>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
              </svg>
            </template>
            {{ inWatchlist ? t('show_in_watchlist') : t('show_add_watchlist') }}
          </ActionGhostButton>
          <AddToListPopover
            :media-type="MEDIA_TYPE.MOVIE"
            :tmdb-id="Number(route.params.id)"
            @added="() => showSuccess(t('list_added_short'))"
          />
          <template #rating>
            <StarRating v-if="canRate" v-model="userRating" @update:modelValue="submitRating" />
            <p v-else class="text-xs text-muted">{{ t('rating_movie_requires_watched') }}</p>
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
                <p class="text-xs text-gray-500 mb-2 uppercase tracking-wider">{{ t('movie_watch_now') }}</p>
                <div class="flex flex-wrap gap-2">
                  <div
                    v-for="p in (movie.watch_providers.flatrate || []).slice(0, 6)"
                    :key="`provider-${p.provider_id}`"
                    class="inline-flex items-center gap-2 rounded-lg border border-surface-200 bg-surface-100/70 px-2.5 py-2 text-sm text-secondary max-w-full"
                  >
                    <img v-if="p.logo_path" :src="tmdbImageUrl(p.logo_path, 'w92') || ''" :alt="`${p.provider_name} logo`" class="h-10 w-10 rounded-md object-cover shrink-0" loading="lazy" decoding="async" />
                    <span class="truncate">{{ p.provider_name }}</span>
                  </div>
                  <span v-if="!(movie.watch_providers.flatrate || []).length" class="text-xs text-muted">{{ t('movie_no_providers') }}</span>
                </div>
              </div>
              <div v-if="topCrew.length" class="min-w-0">
                <p class="text-gray-500 text-xs mb-2">{{ t('movie_crew_highlights') }}</p>
                <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <div v-for="person in topCrew" :key="person.credit_id" class="text-gray-400 max-w-full break-words">
                    <span class="text-gray-500">{{ person.job }}:</span>
                    <RouterLink
                      :to="`/people/${person.id}`"
                      class="text-secondary hover:text-brand-400 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 rounded-sm"
                    >{{ person.name }}</RouterLink>
                  </div>
                </div>
              </div>
            </div>
            <div class="space-y-4 min-w-0">
              <div class="card p-4">
                <p class="text-xs text-gray-500 uppercase tracking-wider mb-2">{{ t('movie_details') }}</p>
                <dl class="text-sm space-y-1.5">
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('movie_status') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ movie.status || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('movie_runtime') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ runtimeLabel || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('movie_released') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ formatDateByLocale(movie.release_date) || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('movie_language') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ movie.language || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('movie_post_credits') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ movie.has_postcredits_scene ? 'Yes' : 'No' }}</dd>
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
                  {{ refreshingMetadata ? 'Updating metadata...' : 'Update metadata from TMDB' }}
                </button>
                <p class="text-xs text-muted break-words">
                  Last metadata update: {{ metadataUpdatedAtLabel }}
                </p>
              </div>
            </div>
          </div>

          <div class="mt-8">
            <h3 class="text-primary font-medium mb-3">{{ t('movie_top_cast') }}</h3>
            <CastGrid :people="(creditsData?.cast || []).slice(0, 8)" />
            <button v-if="(creditsData?.cast || []).length > 8" type="button" class="mt-3 text-sm text-brand-400 hover:text-brand-300" @click="setTab('cast')">
              {{ t('movie_view_all_cast') }}
            </button>
          </div>
        </template>

        <template v-else-if="activeTab === 'cast'">
          <p v-if="creditsError" class="text-sm text-muted mb-3">{{ t('common_credits_unavailable') }}
            <button type="button" class="text-brand-400 hover:text-brand-300" @click="reloadCredits">{{ t('action_try_again') }}</button>
          </p>
          <h3 class="text-primary font-medium mb-3">Cast{{ creditsData?.cast?.length ? ` (${creditsData.cast.length})` : '' }}</h3>
          <CastGrid :people="creditsData?.cast || []" />
          <div v-if="(creditsData?.crew || []).length" class="mt-8">
            <h3 class="text-primary font-medium mb-3">{{ t('movie_crew') }}</h3>
            <CastGrid :people="creditsData?.crew || []" :empty-label="t('movie_no_crew')" />
          </div>
        </template>

        <template v-else-if="activeTab === 'collection'">
          <CollectionStrip :collection="collectionDetail" :loading="loadingCollection" :error="collectionError" @retry="loadCollection" />
        </template>

        <template v-else-if="activeTab === 'history'">
          <MediaHistoryTab :filter="historyFilter" />
        </template>

        <template v-else-if="activeTab === 'more'">
          <p v-if="recsError" class="text-sm text-muted mb-3">{{ t('common_recs_unavailable') }}</p>
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
import FlashToast from '@/components/FlashToast.vue'
import LoadError from '@/components/LoadError.vue'
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
import { useDetailTabs } from '@/composables/useDetailTabs'
import { useRecommendations } from '@/composables/useRecommendations'
import { useUserRating } from '@/composables/useUserRating'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { tmdbImageUrl } from '@/utils/images'
import { formatUpdatedAtLabel } from '@/utils/mediaStatus'
import { formatHoursMinutes } from '@/utils/progress'
import { movieExternalLinks } from '@/utils/externalLinks'
import { instantEpochMs, instantFromEpochMs, temporalYear } from '@/utils/temporal'
import { watchedTooltipText } from '@/utils/watchOptions'
import type { CollectionDetail, AggregateCredits, MediaResult, Movie, PaginatedResponse, WatchEntry } from '@/types/api'
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
const creditsData = ref<AggregateCredits | null>(null)
const collectionDetail = ref<CollectionDetail | null>(null)
const loading = ref(true)
const loadError = ref('')
const loadingCollection = ref(false)
const collectionError = ref(false)
const creditsError = ref(false)
const watchedCount = ref(0)
const latestWatchedAt = ref('')
const inWatchlist = ref(false)
const watchlistTitle = computed(() => getWatchlistAriaLabel(MEDIA_TYPE.MOVIE, inWatchlist.value, movie.value?.user_status?.status_changed_at ?? null))
const metadataFlash = useFlashMessages()
const {
  successMsg: metadataSuccessMsg,
  errorMsg: metadataErrorMsg,
  showSuccess: showMetadataSuccess,
  showError: showMetadataError,
} = metadataFlash
const { successMsg, errorMsg, showSuccess, showError } = useFlashMessages()

const { recommendations, loadingRecs, recsError, loadRecommendations, handleRecommendationStatusChanged } = useRecommendations(
  (id) => mediaAPI.getMovieRecommendations(id),
  MEDIA_TYPE.MOVIE,
  () => movieId.value,
)

const { userRating, canRate, submitRating } = useUserRating({
  mediaType: MEDIA_TYPE.MOVIE,
  getId: () => movieId.value,
  getStatus: () => movie.value?.user_status?.status,
  getRateErrorMessage: () => t('rating_movie_requires_watched'),
  getRatedMessage: (score) => t('rating_rated_score', { score }),
  notifySuccess: showSuccess,
  notifyError: showError,
})
const unwatchDialog = ref<InstanceType<typeof MovieUnwatchDialog> | null>(null)
const refreshingMetadata = ref(false)

const {
  showDatePicker,
  pickerInitialValue,
  handleQuickAction: runQuickAction,
  getWatchlistAriaLabel,
  handleWatchOption: runWatchOption,
  handleDatePickerConfirm,
  handleDatePickerCancel,
} = useMediaCardQuickActions({ onError: showError })

const watchedMessage = computed(() => {
  if (isDropped.value) return t('watch_action_dropped')
  return watchedCount.value > 0 ? t('watch_action_watched') : t('watch_action_watch')
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

const topCrew = computed(() => {
  const crew = creditsData.value?.crew || []
  const priority = ['Director', 'Writer', 'Screenplay', 'Novel', 'Producer']
  return crew
    .filter((p) => priority.includes(p.job || ''))
    .sort((a, b) => priority.indexOf(a.job || '') - priority.indexOf(b.job || ''))
    .slice(0, 6)
})

const { activeTab, visibleTabs, setTab } = useDetailTabs(['overview', 'cast', 'collection', 'history', 'more'] as const, () => {
  const tabs: MediaTab[] = [
    { id: 'overview', label: t('tabs_overview') },
    { id: 'cast', label: t('tabs_cast'), count: creditsData.value?.cast?.length },
    { id: 'history', label: t('tabs_history') },
  ]
  if (movie.value?.collection?.id) {
    tabs.push({ id: 'collection', label: t('tabs_collection') })
  }
  // "More like this" only while loading or when there are recommendations; hidden when empty or failed.
  if (recommendations.value.length > 0 || loadingRecs.value) {
    tabs.push({ id: 'more', label: t('tabs_more') })
  }
  return tabs
})

function releaseYear(value: string | null | undefined) {
  if (!value) return ''
  return temporalYear(value) || ''
}

function applyWatchHistory(response: PaginatedResponse<WatchEntry>) {
  const entries = response.results
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
    showError(getApiErrorMessage(e, t('history_load_failed')))
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
  showSuccess(t('movie_removed_history'))
}

async function loadCollection() {
  const collectionId = movie.value?.collection?.id
  if (!collectionId) return
  loadingCollection.value = true
  collectionError.value = false
  try {
    collectionDetail.value = await mediaAPI.getCollection(collectionId)
  } catch {
    collectionDetail.value = null
    collectionError.value = true
  } finally {
    loadingCollection.value = false
  }
}

async function reloadCredits() {
  creditsError.value = false
  try {
    creditsData.value = await mediaAPI.getMovieCredits(movieId.value)
  } catch {
    creditsError.value = true
  }
}


async function loadMovie(): Promise<boolean> {
  loading.value = true
  loadError.value = ''
  creditsError.value = false
  try {
    const [movieRes, creditsRes] = await Promise.all([
      mediaAPI.getMovie(movieId.value),
      mediaAPI.getMovieCredits(movieId.value).catch(() => {
        creditsError.value = true
        return null
      }),
    ])
    movie.value = movieRes
    creditsData.value = creditsRes
    void loadCollection()
    void loadRecommendations()
    return true
  } catch (error: unknown) {
    loadError.value = getApiErrorMessage(error, t('error_load_movie'))
    return false
  } finally {
    loading.value = false
  }
}

async function loadPage() {
  if (!(await loadMovie())) return

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
      const found = ratingRes.value.results[0]
      if (found) userRating.value = found.score
    }
  }
}

onMounted(loadPage)

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
  latestWatchedAt.value = movie.value?.user_status?.watched_at ?? ''
  showSuccess(t('movie_marked_watched'))
}

async function handleDropMovie() {
  if (!movie.value) {
    return
  }
  try {
    await trackingAPI.dropMedia({ tmdb_id: movieId.value, media_type: MEDIA_TYPE.MOVIE })
    movie.value = await mediaAPI.getMovie(movieId.value)
    inWatchlist.value = false
    showSuccess(t('movie_dropped'))
  } catch (error) {
    showError(getApiErrorMessage(error, t('movie_drop_failed')))
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
  showSuccess(result === 'removed' ? t('show_removed_watchlist') : t('show_added_watchlist'))
}

async function refreshMetadata() {
  if (refreshingMetadata.value) return
  refreshingMetadata.value = true
  try {
    await mediaAPI.refreshMovie(movieId.value)
    movie.value = await mediaAPI.getMovie(movieId.value)
    inWatchlist.value = movie.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
    showMetadataSuccess(t('metadata_updated_movie'))
  } catch (error) {
    showMetadataError(getApiErrorMessage(error, t('movie_refresh_failed')))
  } finally {
    refreshingMetadata.value = false
  }
}
</script>
