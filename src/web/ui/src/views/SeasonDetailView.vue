<template>
  <div>
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      :title="t('picker_when_season')"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <EpisodeUnwatchDialog ref="unwatchDialog" :on-error="showActionError" @unwatched="onEpisodeUnwatched" />

    <FlashToast :messages="[{ text: actionError, kind: 'error' }]" />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
      <router-link :to="{ name: 'tv-detail', params: { id: route.params.id }, query: { tab: 'seasons' } }" class="text-muted text-sm hover:text-brand-400 transition inline-flex items-center gap-1 mb-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
        {{ t('season_back_to', { name: showName }) }}
      </router-link>
    </div>

    <DetailHero
      bare
      :poster-url="season?.poster_url"
      :poster-alt="season && season.season_number === 0 ? t('episode_special_season') : (season?.name ?? '')"
      :loading="loading"
    >
      <template #eyebrow>
        <RouterLink :to="{ name: 'tv-detail', params: { id: route.params.id } }" class="text-xs text-gray-500 uppercase tracking-wider mb-3 hover:text-brand-400 transition inline-block">
          {{ showName }}
        </RouterLink>
      </template>
      <template #title>
        <h1 v-if="season" class="font-display text-3xl md:text-5xl text-primary font-semibold mb-1">{{ season.season_number === 0 ? t('episode_special_season') : season.name }}</h1>
      </template>
      <template #meta>
        <p v-if="season" class="text-muted text-sm mb-3">
          {{ t('season_season') }} {{ seasonNumber }} · {{ totalEpisodesCount }} {{ totalEpisodesCount === 1 ? t('common_episode_one') : t('common_episode_many') }}{{ seasonAirYear ? ` · ${seasonAirYear}` : '' }} · {{ seasonProgressFraction }} {{ t('show_season_progress_watched') }}
        </p>
      </template>
      <template #badges>
        <div v-if="hasSeasonRating" class="flex items-center gap-4 mb-1 text-sm">
          <RatingBadge :value="season?.vote_average ?? 0" :votes="season?.vote_count ?? 0" out-of-ten />
        </div>
      </template>
      <template #description>
        <p v-if="season?.overview" class="text-secondary leading-relaxed mt-4 mb-4 max-w-2xl line-clamp-3">{{ season.overview }}</p>
      </template>
      <template #links>
        <ExternalLinks
          v-if="season"
          :tmdb-url="externalLinks.tmdbUrl"
          :tvmaze-url="externalLinks.tvmazeUrl"
          :imdb-url="externalLinks.imdbUrl"
          class="mb-4"
        />
      </template>
      <template #actions>
        <div v-if="season" class="flex flex-wrap gap-2 mb-4">
          <WatchSplitButton
            v-if="auth.isAuthenticated"
            :active="seasonProgress === 100"
            :label="seasonProgress === 100 ? 'Season watched' : `${seasonProgressFraction} · Watch`"
            :release-date="season.air_date ? String(season.air_date) : ''"
            @trigger="handleSeasonWatchOption('now')"
            @select="handleSeasonWatchOption"
          />
          <p v-else class="text-white text-lg font-medium">{{ seasonProgressFraction }}</p>
        </div>
      </template>
      <template #belowActions>
        <ProgressBar v-if="season" :pct="seasonProgress" class="mt-2 max-w-2xl" />
      </template>
    </DetailHero>

    <div v-if="!loading && season" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
      <MediaTabs v-model="activeTab" :tabs="visibleTabs" aria-label="Season sections" />

        <div class="mt-6" role="tabpanel" :id="`tabpanel-${activeTab}`" :aria-labelledby="`tab-${activeTab}`">
          <template v-if="activeTab === 'overview'">
            <div class="grid md:grid-cols-3 gap-8">
              <div class="md:col-span-2 space-y-6">
                <div>
                  <h3 class="text-primary font-medium mb-3">{{ t('tabs_overview') }}</h3>
                  <p v-if="season.overview" class="text-secondary leading-relaxed max-w-2xl">{{ season.overview }}</p>
                  <p v-else class="text-muted text-sm">{{ t('season_no_overview') }}</p>
                </div>
              </div>
              <div class="space-y-4">
                <div class="card p-4">
                  <p class="text-xs text-gray-500 uppercase tracking-wider mb-2">{{ t('season_details') }}</p>
                  <dl class="text-sm space-y-1.5">
                    <div class="flex justify-between gap-2"><dt class="text-muted">{{ t('season_show') }}</dt><dd class="text-secondary truncate max-w-[60%]">{{ showName }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">{{ t('season_season') }}</dt><dd class="text-secondary">{{ seasonNumber }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">{{ t('tabs_episodes') }}</dt><dd class="text-secondary">{{ totalEpisodesCount }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">{{ t('season_aired') }}</dt><dd class="text-secondary">{{ seasonAirYear || '—' }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">{{ t('season_watched') }}</dt><dd class="text-secondary">{{ seasonProgressFraction }}</dd></div>
                  </dl>
                </div>
              </div>
            </div>

            <div class="mt-8">
              <h3 class="text-primary font-medium mb-3">{{ t('season_top_cast') }}</h3>
              <CastGrid :people="displayCast.slice(0, 8)" />
              <button v-if="displayCast.length > 8" type="button" class="mt-3 text-sm text-brand-400 hover:text-brand-300" @click="setTab('cast')">
                {{ t('season_view_all_cast') }}
              </button>
            </div>
          </template>

          <template v-else-if="activeTab === 'episodes'">
            <h3 class="text-primary font-medium mb-3">{{ t('tabs_episodes') }}</h3>
            <SeasonEpisodeList
              v-if="season?.episodes?.length"
              :episodes="season.episodes"
              :tmdb-id="tmdbId"
              :season-number="seasonNumber"
              :is-episode-watched="isEpisodeWatched"
              :get-episode-watched-at="getEpisodeWatchedAt"
              @watch-option="handleEpisodeWatchOption"
              @unwatch="openUnwatchConfirm"
            />
            <div v-else-if="!loading" class="text-center py-16 text-muted">
              <p>{{ t('season_no_episodes') }}</p>
            </div>
          </template>

          <template v-else-if="activeTab === 'cast'">
            <h3 class="text-primary font-medium mb-3">Season cast{{ displayCast.length ? ` (${displayCast.length})` : '' }}</h3>
            <p v-if="creditsError && !displayCast.length" class="text-sm text-muted mb-3">{{ t('common_credits_unavailable') }}
              <button type="button" class="text-brand-400 hover:text-brand-300" @click="reloadCredits">{{ t('action_try_again') }}</button>
            </p>
            <CastGrid :people="displayCast" />
          </template>

          <template v-else-if="activeTab === 'history'">
            <MediaHistoryTab :filter="historyFilter" />
          </template>
        </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { mediaAPI, trackingAPI } from '@/api'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { useAuthStore } from '@/stores/auth'
import ProgressBar from '@/components/ProgressBar.vue'
import FlashToast from '@/components/FlashToast.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchSplitButton from '@/components/WatchSplitButton.vue'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import ExternalLinks from '@/components/ExternalLinks.vue'
import CastGrid from '@/components/CastGrid.vue'
import DetailHero from '@/components/DetailHero.vue'
import MediaTabs, { type MediaTab } from '@/components/MediaTabs.vue'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { useI18n } from '@/i18n'
import { useDetailTabs } from '@/composables/useDetailTabs'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { useWatchedEpisodes } from '@/composables/useWatchedEpisodes'
import { getApiErrorMessage } from '@/utils/errors'
import { computeProgressPercent, formatProgressFraction } from '@/utils/progress'
import { seasonExternalLinks } from '@/utils/externalLinks'
import { temporalYear } from '@/utils/temporal'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'
import type { AggregateCredits, Season } from '@/types/api'
import type { WatchedAtOption } from '@/utils/watchOptions'

type EpisodeTarget = { episodeNumber: number }

const route = useRoute()
const { t } = useI18n()
const router = useRouter()
const tmdbId = computed(() => Number.parseInt(String(route.params.id), 10))
const seasonNumber = computed(() => Number.parseInt(String(route.params.seasonNumber), 10))
const historyFilter = computed(() => ({
  media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
  tmdb_id: tmdbId.value,
  season_number: seasonNumber.value,
}))
const auth = useAuthStore()
const season = ref<Season | null>(null)
const aggregateCredits = ref<AggregateCredits | null>(null)
const creditsError = ref(false)
const loading = ref(true)
const showName = ref('TV Show')
const unwatchDialog = ref<InstanceType<typeof EpisodeUnwatchDialog> | null>(null)
const { errorMsg: actionError, showError: showActionError } = useFlashMessages()
const {
  showDatePicker,
  pickerInitialValue,
  pickWatchedDateTime,
  handleDatePickerConfirm,
  handleDatePickerCancel,
  markFromOption,
} = useEpisodeWatchActions({ onError: showActionError })
const {
  watchedEps,
  isWatched,
  watchedAt,
  markLocally,
  unmarkLocally,
  load: loadWatchedEpisodes,
} = useWatchedEpisodes()

// Watched count comes from the backend (`user_status.progress`) and is
// adjusted locally as episodes are marked/unmarked.
const watchedEpisodesCount = ref(0)


const seasonCredits = computed((): AggregateCredits | null => season.value?.credits ?? null)

const displayCast = computed(() => {
  if (aggregateCredits.value?.cast?.length) return aggregateCredits.value.cast
  return seasonCredits.value?.cast ?? []
})

const displayCrew = computed(() => {
  if (aggregateCredits.value?.crew?.length) return aggregateCredits.value.crew
  return seasonCredits.value?.crew ?? []
})

const externalLinks = computed(() => seasonExternalLinks(
  tmdbId.value,
  seasonNumber.value,
  season.value?.external_ids,
  season.value?.show_external_ids,
))

const seasonAirYear = computed(() => {
  const airDate = season.value?.air_date
  return airDate ? temporalYear(String(airDate)) || '' : ''
})

const hasSeasonRating = computed(() => (season.value?.vote_average ?? 0) > 0)

function countWatchedInSeasonFromSet(seasonNum: number) {
  const prefix = `${seasonNum}-`
  let count = 0
  for (const key of watchedEps.value) {
    if (key.startsWith(prefix)) count++
  }
  return count
}

const seasonProgress = computed(() => {
  if (!season.value?.episodes?.length) return 0
  return computeProgressPercent(watchedEpisodesCount.value, totalEpisodesCount.value)
})

const totalEpisodesCount = computed(() => season.value?.episodes?.length || 0)

const { activeTab, visibleTabs, setTab } = useDetailTabs(['overview', 'episodes', 'cast', 'history'] as const, () => [
  { id: 'overview', label: t('tabs_overview') },
  { id: 'episodes', label: t('tabs_episodes'), count: totalEpisodesCount.value || undefined },
  { id: 'cast', label: t('tabs_cast'), count: displayCast.value.length || undefined },
  { id: 'history', label: t('tabs_history') },
])

const seasonProgressFraction = computed(() => {
  return formatProgressFraction(watchedEpisodesCount.value, totalEpisodesCount.value)
})

function isEpisodeWatched(epNum: number) {
  return isWatched(seasonNumber.value, epNum)
}

function getEpisodeWatchedAt(epNum: number) {
  return watchedAt(seasonNumber.value, epNum)
}

function openUnwatchConfirm(payload: EpisodeTarget) {
  unwatchDialog.value?.open({
    tmdbId: tmdbId.value,
    seasonNumber: seasonNumber.value,
    episodeNumber: payload.episodeNumber,
  })
}

function onEpisodeUnwatched(target: { seasonNumber: string | number; episodeNumber: string | number }) {
  const season = Number(target.seasonNumber)
  const episode = Number(target.episodeNumber)
  if (isWatched(season, episode)) {
    watchedEpisodesCount.value = Math.max(0, watchedEpisodesCount.value - 1)
  }
  unmarkLocally(season, episode)
}

async function handleEpisodeWatchOption(payload: EpisodeTarget & { option: WatchedAtOption; releaseDate: string | null }) {
  const epNum = payload.episodeNumber
  const sn = seasonNumber.value

  const wasWatched = isEpisodeWatched(epNum)
  const marked = await markFromOption(payload.option, {
    tmdbId: tmdbId.value,
    seasonNumber: sn,
    episodeNumber: epNum,
  }, { pickerInitial: getEpisodeWatchedAt(epNum) })
  if (!marked) return

  markLocally(sn, epNum, marked.watchedAt)
  if (!wasWatched) watchedEpisodesCount.value += 1
}

async function handleSeasonWatchOption(option: WatchedAtOption) {
  const resolution = await resolveWatchedAtFromOption(option, {
    pickDateTime: () => pickWatchedDateTime(''),
  })
  if (resolution.cancelled) {
    return
  }

  try {
    await trackingAPI.markSeasonWatched({
      tmdb_id: tmdbId.value,
      season_number: seasonNumber.value,
      watched_at: resolution.watchedAt ?? undefined,
    })
    await loadWatchedEpisodes(tmdbId.value, {
      seasonNumber: seasonNumber.value,
      onError: (error: unknown) => showActionError(getApiErrorMessage(error, t('history_load_failed'))),
    })
    watchedEpisodesCount.value = countWatchedInSeasonFromSet(seasonNumber.value)
  } catch (error: unknown) {
    showActionError(getApiErrorMessage(error, t('error_mark_season')))
  }
}

async function reloadCredits() {
  creditsError.value = false
  try {
    aggregateCredits.value = await mediaAPI.getSeasonCredits(tmdbId.value, seasonNumber.value)
  } catch {
    creditsError.value = true
  }
}

onMounted(async () => {
  try {
    const [data, credits] = await Promise.all([
      mediaAPI.getSeason(tmdbId.value, seasonNumber.value),
      mediaAPI.getSeasonCredits(tmdbId.value, seasonNumber.value).catch(() => {
        creditsError.value = true
        return null
      }),
    ])
    if (data) {
      season.value = data
      showName.value = data.show_name || 'TV Show'
      watchedEpisodesCount.value = data.user_status?.progress?.watched_episodes ?? 0
    }
    aggregateCredits.value = credits
  } finally {
    loading.value = false
  }

  if (auth.isAuthenticated) {
    await loadWatchedEpisodes(tmdbId.value, {
      seasonNumber: seasonNumber.value,
      onError: (error: unknown) => showActionError(getApiErrorMessage(error, t('history_load_failed'))),
    })
  }
})
</script>
