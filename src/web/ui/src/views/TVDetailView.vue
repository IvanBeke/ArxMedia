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
      :title="t('picker_when_episode')"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <ConfirmDialog
      ref="removeHistoryDialog"
      title="Remove from watched history?"
      message="This will remove all watched episodes for this show from your history. Ratings and list membership are not changed."
      confirm-label="Remove"
      cancel-label="Keep history"
      loading-label="Removing..."
      :loading="removingHistory"
      @confirm="confirmRemoveWatchedEpisodes"
    />

    <EpisodeUnwatchDialog ref="unwatchEpisodeDialog" :on-error="showError" @unwatched="onEpisodeUnwatched" />

    <div v-if="loadError" class="max-w-3xl mx-auto px-4 py-16">
      <LoadError :message="loadError" @retry="loadPage" />
    </div>

    <DetailHero
      v-else
      :backdrop-url="show?.backdrop_url"
      :backdrop-alt="show?.name"
      :poster-url="show?.poster_url"
      :poster-alt="show?.name"
      :loading="loading"
    >
      <template #eyebrow>
        <div v-if="show" class="flex flex-wrap gap-2 mb-3">
          <span v-for="g in show.genres" :key="g.id" class="badge bg-surface-200 text-secondary text-xs">{{ g.name }}</span>
        </div>
      </template>
      <template #title>
        <h1 v-if="show" class="font-display text-3xl md:text-5xl text-primary font-semibold mb-1 break-words">{{ show.name }}</h1>
      </template>
      <template #meta>
        <template v-if="show">
          <p class="text-muted text-sm mb-3">
            {{ show.first_air_date ? (temporalYear(show.first_air_date) || '') : '' }}
            · {{ show.number_of_seasons }} Season{{ show.number_of_seasons !== 1 ? 's' : '' }}
            <template v-if="auth.isAuthenticated"> · {{ showWatchedFraction }} watched</template>
            <template v-else> · {{ show.number_of_episodes }} Episode{{ show.number_of_episodes !== 1 ? 's' : '' }}</template>
            <span v-if="show.episode_runtime"> · {{ show.episode_runtime }} min/ep</span>
            <span v-if="show.status"> · {{ show.status }}</span>
          </p>
          <div class="flex items-center gap-4 mb-1 text-sm">
            <RatingBadge :value="show.vote_average ?? 0" :votes="show.vote_count" out-of-ten />
          </div>
          <p v-if="show.networks" class="text-muted text-sm mt-2 break-words">{{ displayNetworks }}</p>
        </template>
      </template>
      <template #description>
        <p v-if="show" class="text-secondary leading-relaxed mt-4 mb-4 max-w-2xl break-words">{{ show.overview }}</p>
      </template>
      <template #links>
        <ExternalLinks
          v-if="show"
          :tmdb-url="externalLinks.tmdbUrl"
          :tvmaze-url="externalLinks.tvmazeUrl"
          :imdb-url="externalLinks.imdbUrl"
          class="mb-4"
        />
      </template>
      <template #actions>
        <MediaActionsBar v-if="show && auth.isAuthenticated">
          <WatchSplitButton
            :active="showStatus === WATCH_ENTRY_STATUS.WATCHING || showStatus === WATCH_ENTRY_STATUS.WATCHED"
            :variant="showStatus === WATCH_ENTRY_STATUS.DROPPED ? 'danger' : 'default'"
            :label="watchButtonLabel"
            :release-date="show?.first_air_date ?? ''"
            :loading="showMarking"
            @trigger="handleWatchingAction"
            @select="handleShowWatchOption"
          >
            <template #menuFooter>
              <div v-if="showStatus === WATCH_ENTRY_STATUS.WATCHING || showStatus === WATCH_ENTRY_STATUS.WATCHED">
                <button
                  type="button"
                  @click="handleRemoveWatchedEpisodes"
                  class="block w-full px-3 py-2 text-left text-sm text-muted hover:bg-surface-200 hover:text-primary transition-colors rounded"
                >
                  {{ t('show_remove_episodes') }}
                </button>
                <button
                  type="button"
                  @click="handleDropShow"
                  class="block w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-surface-200 hover:text-red-300 transition-colors rounded"
                >
                  {{ t('show_drop') }}
                </button>
              </div>
              <div v-else>
                <button
                  type="button"
                  @click="handleWatchingAction"
                  class="block w-full px-3 py-2 text-left text-sm text-muted hover:bg-surface-200 hover:text-primary transition-colors rounded"
                >
                  {{ t('show_set_watching') }}
                </button>
              </div>
            </template>
          </WatchSplitButton>
          <ActionGhostButton v-if="showStatus !== WATCH_ENTRY_STATUS.WATCHING && !hasWatchedEpisodes" :active="showStatus === 'watchlist'" :title="watchlistTitle" @click="handleWatchlistAction">
            <template #icon>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
              </svg>
            </template>
            {{ showStatus === 'watchlist' ? t('show_in_watchlist') : t('show_add_watchlist') }}
          </ActionGhostButton>
          <AddToListPopover
            :media-type="MEDIA_TYPE.TV"
            :tmdb-id="tmdbId"
            @added="() => showSuccess(t('list_added_short'))"
          />
          <template #rating>
            <StarRating v-if="canRate" v-model="userRating" @update:modelValue="submitRating" />
            <p v-else class="text-xs text-muted">{{ t('rating_show_requires_watching') }}</p>
          </template>
        </MediaActionsBar>
      </template>
      <template #belowActions>
        <ProgressBar v-if="show && auth.isAuthenticated" :pct="showProgress" class="mt-2 max-w-2xl" />
      </template>
    </DetailHero>

    <div v-if="!loading && show" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
      <MediaTabs v-model="activeTab" :tabs="visibleTabs" aria-label="Show sections" />

      <div class="mt-6" role="tabpanel" :id="`tabpanel-${activeTab}`" :aria-labelledby="`tab-${activeTab}`">
        <template v-if="activeTab === 'overview'">
          <div class="grid md:grid-cols-3 gap-8">
            <div class="md:col-span-2 space-y-6 min-w-0">
              <div>
                <h3 class="text-primary font-medium mb-3">{{ t('show_synopsis') }}</h3>
                <p class="text-secondary leading-relaxed break-words">{{ show?.overview }}</p>
              </div>
              <div v-if="show.watch_providers" class="min-w-0">
                <p class="text-xs text-gray-500 mb-2 uppercase tracking-wider">{{ t('show_watch_now') }}</p>
                <div class="flex flex-wrap gap-2">
                  <div
                    v-for="p in (show.watch_providers.flatrate || []).slice(0, 6)"
                    :key="`provider-${p.provider_id}`"
                    class="inline-flex items-center gap-2 rounded-lg border border-surface-200 bg-surface-100/70 px-2.5 py-2 text-sm text-secondary max-w-full"
                  >
                    <img v-if="p.logo_path" :src="tmdbImageUrl(p.logo_path, 'w92') || ''" :alt="`${p.provider_name} logo`" class="h-10 w-10 rounded-md object-cover shrink-0" loading="lazy" decoding="async" />
                    <span class="truncate">{{ p.provider_name }}</span>
                  </div>
                  <span v-if="!(show.watch_providers.flatrate || []).length" class="text-xs text-muted">{{ t('show_no_providers') }}</span>
                </div>
              </div>
            </div>
            <div class="space-y-4 min-w-0">
              <div class="card p-4">
                <p class="text-xs text-gray-500 uppercase tracking-wider mb-2">{{ t('show_details') }}</p>
                <dl class="text-sm space-y-1.5">
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('show_status') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ show.status || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('show_network') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ displayNetworks || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('show_first_aired') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ show.first_air_date || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('show_last_aired') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ show.last_air_date || '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('show_runtime') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ show.episode_runtime ? `${show.episode_runtime} min/ep` : '—' }}</dd>
                  </div>
                  <div class="flex justify-between gap-2">
                    <dt class="text-muted shrink-0">{{ t('show_language') }}</dt>
                    <dd class="text-secondary truncate min-w-0 max-w-[60%]">{{ show.language || '—' }}</dd>
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
            <h3 class="text-primary font-medium mb-3">{{ t('show_top_cast') }}</h3>
            <CastGrid :people="(aggregateCredits?.cast || []).slice(0, 8)" />
            <button v-if="(aggregateCredits?.cast || []).length > 8" type="button" class="mt-3 text-sm text-brand-400 hover:text-brand-300" @click="setTab('cast')">
              {{ t('show_view_all_cast') }}
            </button>
          </div>
        </template>

        <template v-if="activeTab === 'seasons'">
          <div v-if="loadingSeasons" class="space-y-4">
            <div v-for="n in 3" :key="n" class="h-20 skeleton rounded-lg"></div>
          </div>

          <div v-else-if="show?.seasons?.length" class="space-y-2">
            <div v-for="season in show.seasons" :key="season.season_number" class="card overflow-visible">
              <div class="w-full flex items-center gap-4 p-4">
                <div class="w-12 h-16 rounded-md bg-surface-200 overflow-hidden flex-shrink-0 cursor-pointer" @click="toggleSeason(season.season_number)">
                  <img v-if="season.poster_url" :src="season.poster_url" :alt="season.name" loading="lazy" decoding="async" class="w-full h-full object-cover" />
                  <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-500 p-1">
                    <span class="text-xs font-bold">S{{ season.season_number }}</span>
                  </div>
                </div>

                <div class="flex-1 min-w-0">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <RouterLink :to="`/tv/${tmdbId}/season/${season.season_number}`" class="min-w-0 flex-1 truncate text-primary font-medium hover:text-brand-400 transition-colors">
                      {{ season.season_number === 0 ? t('episode_special_season') : season.name }}
                    </RouterLink>
                    <div class="flex items-center gap-2 shrink-0">
                      <button @click.stop="toggleSeasonWatched(season.season_number)" class="text-xs px-2.5 py-1 rounded-md font-medium transition-colors whitespace-nowrap" :class="getSeasonProgress(season.season_number) === 100 ? 'bg-brand-500 text-white hover:bg-brand-600' : 'bg-surface-200 text-muted hover:text-primary hover:bg-surface-300'">
                        {{ getSeasonProgress(season.season_number) === 100 ? t('show_season_watched') : t('show_season_mark_watched') }}
                      </button>
                      <button @click="toggleSeason(season.season_number)" class="p-1 hover:bg-surface-200 rounded transition-colors" :aria-label="t('show_expand_season', { name: season.name })">
                        <svg class="w-5 h-5 text-muted transition-transform" :class="expandedSeason === season.season_number ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                  <p class="text-muted text-sm mt-0.5">{{ season.episode_count }} {{ season.episode_count === 1 ? t('common_episode_one') : t('common_episode_many') }}{{ season.air_date ? ` · ${temporalYear(season.air_date) || ''}` : '' }}<RatingBadge v-if="season.vote_average" :value="season.vote_average" size="xs" class="ml-2 align-middle" /></p>
                  <p v-if="season.overview" class="text-muted text-xs mt-1 line-clamp-3 break-words">{{ season.overview }}</p>
                  <div class="mt-2">
                    <ProgressBar :pct="getSeasonProgress(season.season_number)" />
                    <p class="text-xs text-muted mt-1">{{ formatSeasonProgressFraction(season.season_number) }} {{ t('show_season_progress_watched') }}</p>
                  </div>
                </div>
              </div>

              <div v-if="expandedSeason === season.season_number" class="border-t border-surface-200">
                <div v-if="seasonLoading === season.season_number" class="p-4 space-y-3">
                  <div v-for="n in 3" :key="n" class="h-20 skeleton rounded-md"></div>
                </div>

                <SeasonEpisodeList
                  v-else-if="seasonEpisodes[season.season_number]?.length"
                  class="p-4"
                  :episodes="seasonEpisodes[season.season_number]"
                  :tmdb-id="tmdbId"
                  :season-number="season.season_number"
                  :is-episode-watched="(episodeNumber) => isWatched(season.season_number, episodeNumber)"
                  :get-episode-watched-at="(episodeNumber) => watchedAt(season.season_number, episodeNumber)"
                  @watch-option="(payload) => handleEpisodeWatchOption(season.season_number, payload)"
                  @unwatch="(payload) => openEpisodeUnwatchConfirm(season.season_number, payload)"
                />

                <div v-else class="p-4 text-center text-muted text-sm">{{ t('show_no_season_episodes') }}</div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'cast'">
          <h3 class="text-primary font-medium mb-3">Cast{{ aggregateCredits?.cast?.length ? ` (${aggregateCredits.cast.length})` : '' }}</h3>
          <div v-if="loadingCredits" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            <div v-for="n in 8" :key="n" class="h-12 skeleton rounded-md"></div>
          </div>
          <CastGrid v-else :people="aggregateCredits?.cast || []" />
          <div v-if="(aggregateCredits?.crew || []).length" class="mt-8">
            <h3 class="text-primary font-medium mb-3">{{ t('show_crew') }}</h3>
            <CastGrid :people="(aggregateCredits?.crew || []).slice(0, 24)" :empty-label="t('show_no_crew')" />
          </div>
        </template>

        <template v-if="activeTab === 'history'">
          <MediaHistoryTab :filter="historyFilter" />
        </template>

        <template v-if="activeTab === 'heatmap'">
          <EpisodeHeatmap :show-id="tmdbId" />
        </template>

        <template v-if="activeTab === 'more'">
          <p v-if="recsError" class="text-sm text-muted mb-3">{{ t('common_recs_unavailable') }}</p>
          <RecommendationsRow :items="recommendations" :media-type="MEDIA_TYPE.TV" :loading="loadingRecs" @status-changed="handleRecommendationStatusChanged" />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { mediaAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import StarRating from '@/components/StarRating.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import AddToListPopover from '@/components/AddToListPopover.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchSplitButton from '@/components/WatchSplitButton.vue'
import ActionGhostButton from '@/components/ActionGhostButton.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import EpisodeHeatmap from '@/components/EpisodeHeatmap.vue'
import DetailHero from '@/components/DetailHero.vue'
import FlashToast from '@/components/FlashToast.vue'
import LoadError from '@/components/LoadError.vue'
import MediaTabs, { type MediaTab } from '@/components/MediaTabs.vue'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import MediaActionsBar from '@/components/MediaActionsBar.vue'
import ExternalLinks from '@/components/ExternalLinks.vue'
import CastGrid from '@/components/CastGrid.vue'
import RecommendationsRow from '@/components/RecommendationsRow.vue'
import { MEDIA_TYPE, WATCH_ENTRY_MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import { getApiErrorMessage } from '@/utils/errors'
import { computeProgressPercent, formatProgressFraction } from '@/utils/progress'
import { tmdbImageUrl } from '@/utils/images'
import { formatUpdatedAtLabel } from '@/utils/mediaStatus'
import { showExternalLinks } from '@/utils/externalLinks'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import { useDetailTabs } from '@/composables/useDetailTabs'
import { useRecommendations } from '@/composables/useRecommendations'
import { useUserRating } from '@/composables/useUserRating'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { useWatchedEpisodes } from '@/composables/useWatchedEpisodes'
import { temporalYear } from '@/utils/temporal'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'
import type { WatchedAtOption } from '@/utils/watchOptions'
import type { Credits, Episode, MediaResult, TVShow } from '@/types/api'
import type { WatchEntryStatus } from '@/types/tracking'

type ShowStatus = WatchEntryStatus | 'watchlist'
type EpisodeTarget = { episodeNumber: number }

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()
const tmdbId = computed(() => Number.parseInt(String(route.params.id), 10))
const historyFilter = computed(() => ({
  media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
  tmdb_id: tmdbId.value,
}))

const show = ref<TVShow | null>(null)
const aggregateCredits = ref<Credits | null>(null)
const loading = ref(true)
const loadError = ref('')
const loadingSeasons = ref(false)
const loadingCredits = ref(false)
const showStatus = ref<ShowStatus>(WATCH_ENTRY_STATUS.NONE)
const watchlistTitle = computed(() => getWatchlistAriaLabel(MEDIA_TYPE.TV, showStatus.value === 'watchlist', show.value?.user_status?.status_changed_at ?? null))
const metadataFlash = useFlashMessages()
const {
  successMsg: metadataSuccessMsg,
  errorMsg: metadataErrorMsg,
  showSuccess: showMetadataSuccess,
  showError: showMetadataError,
} = metadataFlash
const { successMsg, errorMsg, showSuccess, showError } = useFlashMessages()

const { recommendations, loadingRecs, recsError, loadRecommendations, handleRecommendationStatusChanged } = useRecommendations(
  (id) => mediaAPI.getTVRecommendations(id),
  MEDIA_TYPE.TV,
  () => tmdbId.value,
)

const { userRating, canRate, submitRating } = useUserRating({
  mediaType: MEDIA_TYPE.TV,
  getId: () => tmdbId.value,
  getStatus: () => show.value?.user_status?.status,
  getRateErrorMessage: () => t('rating_show_requires_watching'),
  getRatedMessage: (score) => t('rating_rated_score', { score }),
  notifySuccess: showSuccess,
  notifyError: showError,
})
const refreshingMetadata = ref(false)
const removeHistoryDialog = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const removingHistory = ref(false)
const unwatchEpisodeDialog = ref<InstanceType<typeof EpisodeUnwatchDialog> | null>(null)

const { activeTab, visibleTabs, setTab } = useDetailTabs(['overview', 'seasons', 'cast', 'history', 'heatmap', 'more'] as const, () => {
  const tabs: MediaTab[] = [
    { id: 'overview', label: t('tabs_overview') },
    { id: 'seasons', label: t('tabs_seasons') },
    { id: 'cast', label: t('tabs_cast'), count: aggregateCredits.value?.cast?.length },
    { id: 'history', label: t('tabs_history') },
    { id: 'heatmap', label: t('tabs_heatmap') },
  ]
  if (recommendations.value.length > 0 || loadingRecs.value) {
    tabs.push({ id: 'more', label: 'More like this' })
  }
  return tabs
})

const expandedSeason = ref<number | null>(null)
const seasonEpisodes = ref<Record<number, Episode[]>>({})
const seasonLoading = ref<number | null>(null)
const hasWatchedEpisodes = computed(() => watchedEps.value.size > 0)
const {
  handleQuickAction: runQuickAction,
  handleRemoveWatched: runRemoveWatched,
  getWatchlistAriaLabel,
} = useMediaCardQuickActions({ onError: showError })
const {
  showDatePicker,
  pickerInitialValue,
  pickWatchedDateTime,
  handleDatePickerConfirm,
  handleDatePickerCancel,
  markFromOption,
} = useEpisodeWatchActions({ onError: showError })
const {
  watchedEps,
  isWatched,
  watchedAt,
  markLocally,
  unmarkLocally,
  applyResponse: applyWatchedEpisodes,
} = useWatchedEpisodes()

const showMarking = ref(false)

const watchButtonLabel = computed(() => {
  if (showStatus.value === WATCH_ENTRY_STATUS.WATCHING) return t('watch_action_watching')
  if (showStatus.value === WATCH_ENTRY_STATUS.WATCHED) return t('watch_action_watched')
  if (showStatus.value === WATCH_ENTRY_STATUS.DROPPED) return t('watch_action_dropped')
  return t('watch_action_watch')
})

const metadataUpdatedAtLabel = computed(() => formatUpdatedAtLabel(show.value?.metadata_updated_at))

const externalLinks = computed(() => showExternalLinks(tmdbId.value, show.value?.external_ids))

const displayNetworks = computed(() => {
  const networks = show.value?.networks
  if (Array.isArray(networks)) return networks.join(', ')
  return networks || ''
})

const showWatchedCount = computed(() => {
  let count = 0
  for (const key of watchedEps.value) {
    if (!key.startsWith('0-')) count++
  }
  return count
})

const showTotalCount = computed(() => {
  const seasons = show.value?.seasons || []
  if (seasons.length) {
    const regular = seasons
      .filter((season) => season.season_number >= 1)
      .reduce((sum, season) => sum + (season.episode_count || 0), 0)
    if (regular > 0) return regular
  }
  return show.value?.number_of_episodes || 0
})

const showProgress = computed(() => computeProgressPercent(showWatchedCount.value, showTotalCount.value))

const showWatchedFraction = computed(() => formatProgressFraction(showWatchedCount.value, showTotalCount.value))

function syncShowStatusFromUserStatus() {
  const status = show.value?.user_status?.status
  if (status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) {
    showStatus.value = 'watchlist'
    return
  }
  if (
    status === WATCH_ENTRY_STATUS.WATCHING
    || status === WATCH_ENTRY_STATUS.WATCHED
    || status === WATCH_ENTRY_STATUS.DROPPED
  ) {
    showStatus.value = status
    return
  }
  showStatus.value = WATCH_ENTRY_STATUS.NONE
}

function openRemoveHistoryDialog() {
  removeHistoryDialog.value?.showModal()
}

async function handleEpisodeWatchOption(sn: number, payload: EpisodeTarget & { option: WatchedAtOption; releaseDate: string | null }) {
  const epNum = payload.episodeNumber

  const marked = await markFromOption(payload.option, {
    tmdbId: tmdbId.value,
    seasonNumber: sn,
    episodeNumber: epNum,
  }, { pickerInitial: watchedAt(sn, epNum) })
  if (!marked) return

  markLocally(sn, epNum, marked.watchedAt)
  showSuccess(t('show_episode_marked'))
}

function openEpisodeUnwatchConfirm(sn: number, payload: EpisodeTarget) {
  unwatchEpisodeDialog.value?.open({
    tmdbId: tmdbId.value,
    seasonNumber: sn,
    episodeNumber: payload.episodeNumber,
  })
}

async function onEpisodeUnwatched(target: { seasonNumber: string | number; episodeNumber: string | number }) {
  unmarkLocally(Number(target.seasonNumber), Number(target.episodeNumber))
  showSuccess(t('show_episode_unwatched'))
}

function toggleSeason(sn: number) {
  if (expandedSeason.value === sn) {
    expandedSeason.value = null
  } else {
    expandedSeason.value = sn
    loadSeason(sn)
  }
}

async function loadSeason(sn: number) {
  if (seasonEpisodes.value[sn]) return
  seasonLoading.value = sn
  try {
    const data = await mediaAPI.getSeason(tmdbId.value, sn)
    if (data) seasonEpisodes.value[sn] = data.episodes || []
  } catch {
    seasonEpisodes.value[sn] = []
  } finally {
    seasonLoading.value = null
  }
}

function getSeasonProgress(sn: number) {
  const { watched, total } = getSeasonProgressCounts(sn)
  return computeProgressPercent(watched, total)
}

// Watched episodes per season, counted once per change instead of on every progress lookup.
const watchedCountBySeason = computed(() => {
  const counts = new Map<number, number>()
  for (const key of watchedEps.value) {
    const seasonNumber = Number(key.split('-', 1)[0])
    counts.set(seasonNumber, (counts.get(seasonNumber) ?? 0) + 1)
  }
  return counts
})

function getSeasonProgressCounts(sn: number) {
  const watched = watchedCountBySeason.value.get(sn) ?? 0
  const season = show.value?.seasons.find((item) => item.season_number === sn)
  const total = seasonEpisodes.value[sn]?.length || season?.episode_count || watched
  return { watched, total }
}

function formatSeasonProgressFraction(sn: number) {
  const { watched, total } = getSeasonProgressCounts(sn)
  return formatProgressFraction(watched, total)
}

async function toggleSeasonWatched(sn: number) {
  try {
    const progress = getSeasonProgress(sn)
    if (progress === 100) {
      const response = await trackingAPI.unmarkSeasonWatched({ tmdb_id: tmdbId.value, season_number: sn })
      for (const episode of response.episodes) {
        if (episode.season_number !== null && episode.episode_number !== null) {
          unmarkLocally(episode.season_number, episode.episode_number)
        }
      }
      showSuccess(t('show_season_unwatched'))
    } else {
      const response = await trackingAPI.markSeasonWatched({ tmdb_id: tmdbId.value, season_number: sn })
      for (const episode of response.episodes) {
        if (episode.season_number !== null && episode.episode_number !== null) {
          markLocally(episode.season_number, episode.episode_number, episode.watched_at)
        }
      }
      await setShowStatus(WATCH_ENTRY_STATUS.WATCHING)
      showSuccess(t('show_season_marked'))
    }
  } catch (error: unknown) {
    showError(getApiErrorMessage(error, t('error_update_season')))
  }
}

async function setShowStatus(status: ShowStatus): Promise<boolean> {
  if (!show.value) {
    return false
  }

  if (status === WATCH_ENTRY_STATUS.WATCHING && showStatus.value === 'watchlist') {
    await runQuickAction(show.value, MEDIA_TYPE.TV)
    if (show.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) {
      return false
    }
  }

  if (status === WATCH_ENTRY_STATUS.WATCHING) {
    // Show watching status is now determined by watching any episode
  } else if (status === 'watchlist') {
    await runQuickAction(show.value, MEDIA_TYPE.TV)
    if (show.value?.user_status?.status !== WATCH_ENTRY_STATUS.PLAN_TO_WATCH) {
      return false
    }
  } else if (status === WATCH_ENTRY_STATUS.NONE) {
    if (showStatus.value === 'watchlist') {
      await runQuickAction(show.value, MEDIA_TYPE.TV)
      if (show.value?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) {
        return false
      }
    }
  }

  showStatus.value = status
  return true
}

async function handleWatchingAction() {
  if (showStatus.value === WATCH_ENTRY_STATUS.WATCHING) {
    const updated = await setShowStatus(WATCH_ENTRY_STATUS.NONE)
    if (!updated) {
      return
    }
    showSuccess(t('show_removed_watching'))
  } else {
    const updated = await setShowStatus(WATCH_ENTRY_STATUS.WATCHING)
    if (!updated) {
      return
    }
    showSuccess(t('show_added_watching'))
  }
}

async function handleShowWatchOption(option: WatchedAtOption) {
  if (!show.value?.seasons?.length || showMarking.value) {
    return
  }
  const resolution = await resolveWatchedAtFromOption(option, {
    pickDateTime: () => pickWatchedDateTime(''),
  })
  if (resolution.cancelled) {
    return
  }
  showMarking.value = true
  try {
    const response = await trackingAPI.markShowWatched({
      tmdb_id: tmdbId.value,
      watched_at: resolution.watchedAt ?? undefined,
    })
    applyWatchedEpisodes(response)
    seasonEpisodes.value = {}
    await setShowStatus(WATCH_ENTRY_STATUS.WATCHING)
    showSuccess(t('show_marked'))
  } catch (error) {
    showError(getApiErrorMessage(error, t('show_mark_failed')))
  } finally {
    showMarking.value = false
  }
}

async function handleRemoveWatchedEpisodes() {
  openRemoveHistoryDialog()
}

async function confirmRemoveWatchedEpisodes() {
  if (removingHistory.value || !show.value) {
    return
  }
  removingHistory.value = true
  try {
    const removed = await runRemoveWatched(show.value, MEDIA_TYPE.TV)
    if (!removed) {
      return
    }

    watchedEps.value = new Set()
    seasonEpisodes.value = {}
    await loadShow()
    removeHistoryDialog.value?.close()
    showSuccess(t('show_removed_episodes'))
  } finally {
    removingHistory.value = false
  }
}

async function handleDropShow() {
  try {
    await trackingAPI.dropMedia({ tmdb_id: tmdbId.value, media_type: MEDIA_TYPE.TV })
  } catch (error: unknown) {
    showError(getApiErrorMessage(error, t('error_drop_show')))
    return
  }
  await loadShow()
  showSuccess(t('show_dropped'))
}

async function handleWatchlistAction() {
  if (showStatus.value === 'watchlist') {
    const updated = await setShowStatus(WATCH_ENTRY_STATUS.NONE)
    if (!updated) {
      return
    }
    showSuccess(t('show_removed_watchlist'))
  } else {
    const updated = await setShowStatus('watchlist')
    if (!updated) {
      return
    }
    showSuccess(t('show_added_watchlist'))
  }
}

async function loadShow() {
  try {
    const data = await mediaAPI.getTV(tmdbId.value)
    if (data) {
      show.value = data
      syncShowStatusFromUserStatus()
    }
  } catch (error: unknown) {
    // A failed reload after an action keeps the page; only a failed first load replaces it.
    if (!show.value) loadError.value = getApiErrorMessage(error, t('error_load_show'))
  }
}

async function refreshMetadata() {
  if (refreshingMetadata.value) return
  refreshingMetadata.value = true
  try {
    await mediaAPI.refreshTV(tmdbId.value)
    await loadShow()
    seasonEpisodes.value = {}
    showMetadataSuccess(t('metadata_updated_show'))
  } catch (error) {
    showMetadataError(getApiErrorMessage(error, t('movie_refresh_failed')))
  } finally {
    refreshingMetadata.value = false
  }
}

async function loadCredits() {
  loadingCredits.value = true
  try {
    aggregateCredits.value = await mediaAPI.getTVCredits(tmdbId.value)
  } catch (e) {
    console.error('Failed to load credits:', e)
  } finally {
    loadingCredits.value = false
  }
}


async function loadPage() {
  loading.value = true
  loadError.value = ''
  await loadShow()
  loading.value = false
  if (!show.value) return
  void loadCredits()
  void loadRecommendations()

  if (auth.isAuthenticated) {
    const [ratingRes, epsRes] = await Promise.allSettled([
      trackingAPI.getRatings({ media_type: MEDIA_TYPE.TV, tmdb_id: tmdbId.value }),
      trackingAPI.getWatchedEpisodes(tmdbId.value)
    ])

    if (epsRes.status === 'fulfilled' && epsRes.value?.episodes?.length) {
      applyWatchedEpisodes(epsRes.value)
    }

    if (ratingRes.status === 'fulfilled') {
      const found = ratingRes.value.results[0]
      if (found) userRating.value = found.score
    }
  }
}

onMounted(loadPage)
</script>
