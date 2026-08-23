<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this season?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <EpisodeUnwatchDialog ref="unwatchDialog" @unwatched="onEpisodeUnwatched" />

    <!-- Breadcrumb -->
    <router-link :to="{ name: 'tv-detail', params: { id: route.params.id } }" class="text-muted text-sm hover:text-brand-400 transition inline-flex items-center gap-1 mb-6">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
      Back to {{ showName }}
    </router-link>

    <!-- Season header -->
    <div v-if="loading" class="space-y-3 mb-8">
      <div class="h-8 w-48 skeleton rounded-md"></div>
      <div class="h-4 w-72 skeleton rounded-md"></div>
    </div>

    <template v-else-if="season">
      <div class="flex items-end justify-between mb-8">
        <div>
          <h1 class="font-display text-2xl text-primary font-semibold">{{ season.name }}</h1>
          <p class="text-muted text-sm mt-1">{{ season?.episodes?.length || 0 }} episodes{{ season.air_date ? ` · Aired ${temporalYear(season.air_date) || ''}` : '' }}</p>
        </div>
        <div class="text-right flex items-center gap-4">
          <WatchMenu
            v-if="auth.isAuthenticated"
            :release-date="season.air_date"
            @select="handleSeasonWatchOption"
          >
            <div class="text-white text-lg font-medium cursor-pointer">
              {{ seasonProgressFraction }}
            </div>
          </WatchMenu>
          <div v-else>
            <p class="text-white text-lg font-medium">{{ seasonProgressFraction }}</p>
          </div>
          <p class="text-muted text-xs">watched</p>
        </div>
      </div>

      <ProgressBar :pct="seasonProgress" class="mb-8" />

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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { mediaAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import ProgressBar from '@/components/ProgressBar.vue'
import WatchMenu from '@/components/WatchMenu.vue'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { useWatchedEpisodes } from '@/composables/useWatchedEpisodes'
import { getApiErrorMessage } from '@/utils/errors'
import { computeProgressPercent, formatProgressFraction } from '@/utils/progress'
import { temporalYear } from '@/utils/temporal'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'

const route = useRoute()
const tmdbId = computed(() => parseInt(route.params.id))
const seasonNumber = computed(() => parseInt(route.params.seasonNumber))
const auth = useAuthStore()
const season = ref(null)
const loading = ref(true)
const showName = ref('TV Show')
const unwatchDialog = ref(null)
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

const seasonProgress = computed(() => {
  if (!season.value?.episodes?.length) return 0
  return computeProgressPercent(watchedEpisodesCount.value, totalEpisodesCount.value)
})

const watchedEpisodesCount = computed(() => {
  if (!season.value?.episodes?.length) return 0
  return season.value.episodes.filter(ep => watchedEps.value.has(ep.episode_number)).length
})

const totalEpisodesCount = computed(() => season.value?.episodes?.length || 0)

const seasonProgressFraction = computed(() => {
  return formatProgressFraction(watchedEpisodesCount.value, totalEpisodesCount.value)
})

function isEpisodeWatched(epNum) {
  return isWatched(seasonNumber.value, epNum)
}

function getEpisodeWatchedAt(epNum) {
  return watchedAt(seasonNumber.value, epNum)
}

function openUnwatchConfirm(payload) {
  unwatchDialog.value?.open({
    tmdbId: tmdbId.value,
    seasonNumber: seasonNumber.value,
    episodeNumber: payload.episodeNumber,
  })
}

function onEpisodeUnwatched(target) {
  unmarkLocally(target.seasonNumber, target.episodeNumber)
}

async function handleEpisodeWatchOption(payload) {
  const epNum = payload.episodeNumber
  const sn = seasonNumber.value

  const finalWatchedAt = await markFromOption(payload.option, {
    tmdbId: tmdbId.value,
    seasonNumber: sn,
    episodeNumber: epNum,
  }, { releaseDate: payload.releaseDate || '', pickerInitial: getEpisodeWatchedAt(epNum) })
  if (!finalWatchedAt) return

  markLocally(sn, epNum, finalWatchedAt)
}

async function handleSeasonWatchOption(option) {
  const resolution = await resolveWatchedAtFromOption(option, {
    releaseDate: season.value?.air_date || '',
    pickDateTime: () => pickWatchedDateTime(''),
  })
  if (resolution.cancelled) {
    return
  }

  try {
    await trackingAPI.markSeasonWatched({
      tmdb_id: tmdbId.value,
      season_number: seasonNumber.value,
      watched_at: resolution.useReleaseDate ? null : resolution.watchedAt,
      use_release_date: resolution.useReleaseDate,
    })
    await loadWatchedEpisodes(tmdbId.value, { seasonNumber: seasonNumber.value })
  } catch (e) {
    console.error('Failed to mark season:', getApiErrorMessage(e, 'Could not mark season as watched.'))
  }
}

onMounted(async () => {
  try {
    const data = await mediaAPI.getSeason(tmdbId.value, seasonNumber.value)
    if (data) {
      season.value = data
      showName.value = data.show_name || 'TV Show'
    }
  } finally {
    loading.value = false
  }

  if (auth.isAuthenticated) {
    await loadWatchedEpisodes(tmdbId.value, { seasonNumber: seasonNumber.value })
  }
})
</script>
