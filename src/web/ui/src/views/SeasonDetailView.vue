<template>
  <div>
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this season?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <EpisodeUnwatchDialog ref="unwatchDialog" @unwatched="onEpisodeUnwatched" />

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <router-link :to="{ name: 'tv-detail', params: { id: route.params.id }, query: { tab: 'seasons' } }" class="text-muted text-sm hover:text-brand-400 transition inline-flex items-center gap-1 mb-6">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
        Back to {{ showName }}
      </router-link>

      <div v-if="loading" class="space-y-3 mb-8">
        <div class="h-8 w-48 skeleton rounded-md"></div>
        <div class="h-4 w-72 skeleton rounded-md"></div>
      </div>

      <template v-else-if="season">
        <div class="flex flex-col md:flex-row gap-8 mb-8">
          <div class="flex-shrink-0">
            <div class="w-36 md:w-48 rounded-md overflow-hidden shadow-2xl border border-surface-200">
              <img v-if="season.poster_url" :src="season.poster_url" :alt="season.name" class="w-full" />
              <div v-else class="aspect-[2/3] bg-surface-200 flex items-center justify-center text-muted text-sm font-medium p-4 text-center">
                {{ season.name }}
              </div>
            </div>
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs text-gray-500 uppercase tracking-wider mb-1">{{ showName }}</p>
                <h1 class="font-display text-2xl md:text-4xl text-primary font-semibold">{{ season.name }}</h1>
                <p class="text-muted text-sm mt-2">
                  Season {{ seasonNumber }} · {{ totalEpisodesCount }} episode{{ totalEpisodesCount !== 1 ? 's' : '' }}{{ seasonAirYear ? ` · ${seasonAirYear}` : '' }} · {{ seasonProgressFraction }} watched
                </p>
              </div>
              <div class="flex items-center gap-3 shrink-0">
                <WatchSplitButton
                  v-if="auth.isAuthenticated"
                  :active="seasonProgress === 100"
                  :label="seasonProgress === 100 ? 'Season watched' : `${seasonProgressFraction} · Watch`"
                  :release-date="season.air_date ? String(season.air_date) : ''"
                  @trigger="handleSeasonWatchOption('now')"
                  @select="handleSeasonWatchOption"
                />
                <div v-else>
                  <p class="text-white text-lg font-medium">{{ seasonProgressFraction }}</p>
                </div>
                <ExternalLinks
                  :tmdb-url="externalLinks.tmdbUrl"
                  :tvmaze-url="externalLinks.tvmazeUrl"
                  :imdb-url="externalLinks.imdbUrl"
                />
              </div>
            </div>

            <ProgressBar :pct="seasonProgress" class="mt-4 mb-4" />
          </div>
        </div>

        <MediaTabs v-model="activeTab" :tabs="visibleTabs" aria-label="Season sections" />

        <div class="mt-6" role="tabpanel" :id="`tabpanel-${activeTab}`" :aria-labelledby="`tab-${activeTab}`">
          <template v-if="activeTab === 'overview'">
            <div class="grid md:grid-cols-3 gap-8">
              <div class="md:col-span-2 space-y-6">
                <div>
                  <h3 class="text-primary font-medium mb-3">Overview</h3>
                  <p v-if="season.overview" class="text-secondary leading-relaxed max-w-2xl">{{ season.overview }}</p>
                  <p v-else class="text-muted text-sm">No season overview available.</p>
                </div>
                <div>
                  <h3 class="text-primary font-medium mb-3">Top cast</h3>
                  <CastGrid :people="displayCast.slice(0, 8)" />
                  <button v-if="displayCast.length > 8" type="button" class="mt-3 text-sm text-brand-400 hover:text-brand-300" @click="setTab('cast')">
                    View all cast →
                  </button>
                </div>
              </div>
              <div class="space-y-4">
                <div class="card p-4">
                  <p class="text-xs text-gray-500 uppercase tracking-wider mb-2">Details</p>
                  <dl class="text-sm space-y-1.5">
                    <div class="flex justify-between gap-2"><dt class="text-muted">Show</dt><dd class="text-secondary truncate max-w-[60%]">{{ showName }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">Season</dt><dd class="text-secondary">{{ seasonNumber }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">Episodes</dt><dd class="text-secondary">{{ totalEpisodesCount }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">Aired</dt><dd class="text-secondary">{{ seasonAirYear || '—' }}</dd></div>
                    <div class="flex justify-between gap-2"><dt class="text-muted">Watched</dt><dd class="text-secondary">{{ seasonProgressFraction }}</dd></div>
                  </dl>
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="activeTab === 'episodes'">
            <h3 class="text-primary font-medium mb-3">Episodes</h3>
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
              <p>No episodes found for this season.</p>
            </div>
          </template>

          <template v-else-if="activeTab === 'cast'">
            <h3 class="text-primary font-medium mb-3">Season cast{{ displayCast.length ? ` (${displayCast.length})` : '' }}</h3>
            <CastGrid :people="displayCast" />
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mediaAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import ProgressBar from '@/components/ProgressBar.vue'
import WatchSplitButton from '@/components/WatchSplitButton.vue'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import ExternalLinks from '@/components/ExternalLinks.vue'
import CastGrid from '@/components/CastGrid.vue'
import MediaTabs, { type MediaTab } from '@/components/MediaTabs.vue'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { useWatchedEpisodes } from '@/composables/useWatchedEpisodes'
import { getApiErrorMessage } from '@/utils/errors'
import { computeProgressPercent, formatProgressFraction } from '@/utils/progress'
import { seasonExternalLinks } from '@/utils/externalLinks'
import { temporalYear } from '@/utils/temporal'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'
import type { Credits, Season } from '@/types/api'
import type { WatchedAtOption } from '@/utils/watchOptions'

type EpisodeTarget = { episodeNumber: number }

const route = useRoute()
const router = useRouter()
const tmdbId = computed(() => Number.parseInt(String(route.params.id), 10))
const seasonNumber = computed(() => Number.parseInt(String(route.params.seasonNumber), 10))
const auth = useAuthStore()
const season = ref<Season | null>(null)
const aggregateCredits = ref<Credits | null>(null)
const loading = ref(true)
const showName = ref('TV Show')
const unwatchDialog = ref<InstanceType<typeof EpisodeUnwatchDialog> | null>(null)
const {
  showDatePicker,
  pickerInitialValue,
  pickWatchedDateTime,
  handleDatePickerConfirm,
  handleDatePickerCancel,
  markFromOption,
} = useEpisodeWatchActions()
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

const VALID_TABS = ['overview', 'episodes', 'cast'] as const
type SeasonTab = (typeof VALID_TABS)[number]

function initialTab(): SeasonTab {
  const raw = String(route.query.tab || 'overview')
  return (VALID_TABS as readonly string[]).includes(raw) ? (raw as SeasonTab) : 'overview'
}

const activeTab = ref<SeasonTab>(initialTab())

const seasonCredits = computed((): Credits | null => season.value?.credits ?? null)

const displayCast = computed(() => {
  if (aggregateCredits.value?.cast?.length) return aggregateCredits.value.cast
  return seasonCredits.value?.cast ?? []
})

const displayCrew = computed(() => {
  if (aggregateCredits.value?.crew?.length) return aggregateCredits.value.crew
  return seasonCredits.value?.crew ?? []
})

const visibleTabs = computed((): MediaTab[] => {
  const tabs: MediaTab[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'episodes', label: 'Episodes', count: totalEpisodesCount.value || undefined },
    { id: 'cast', label: 'Cast', count: displayCast.value.length || undefined },
  ]
  if (!tabs.some((tab) => tab.id === activeTab.value)) {
    activeTab.value = 'overview'
  }
  return tabs
})

function setTab(tab: SeasonTab) {
  activeTab.value = tab
}

watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

const externalLinks = computed(() => seasonExternalLinks(tmdbId.value, seasonNumber.value))

const seasonAirYear = computed(() => {
  const airDate = season.value?.air_date
  return airDate ? temporalYear(String(airDate)) || '' : ''
})

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
  const finalWatchedAt = await markFromOption(payload.option, {
    tmdbId: tmdbId.value,
    seasonNumber: sn,
    episodeNumber: epNum,
  }, { releaseDate: payload.releaseDate || '', pickerInitial: getEpisodeWatchedAt(epNum) })
  if (!finalWatchedAt) return

  markLocally(sn, epNum, finalWatchedAt)
  if (!wasWatched) watchedEpisodesCount.value += 1
}

async function handleSeasonWatchOption(option: WatchedAtOption) {
  const resolution = await resolveWatchedAtFromOption(option, {
    releaseDate: season.value?.air_date ? String(season.value.air_date) : '',
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
    await loadWatchedEpisodes(tmdbId.value, { seasonNumber: seasonNumber.value })
    watchedEpisodesCount.value = countWatchedInSeasonFromSet(seasonNumber.value)
  } catch (e) {
    console.error('Failed to mark season:', getApiErrorMessage(e, 'Could not mark season as watched.'))
  }
}

onMounted(async () => {
  try {
    const [data, credits] = await Promise.all([
      mediaAPI.getSeason(tmdbId.value, seasonNumber.value),
      mediaAPI.getSeasonCredits(tmdbId.value, seasonNumber.value).catch(() => null),
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
    await loadWatchedEpisodes(tmdbId.value, { seasonNumber: seasonNumber.value })
  }
})
</script>
