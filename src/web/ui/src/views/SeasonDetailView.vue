<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this season?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

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
          <p class="text-muted text-sm mt-1">{{ season?.episodes?.length || 0 }} episodes{{ season.air_date ? ` · Aired ${new Date(season.air_date).getFullYear()}` : '' }}</p>
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
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'
import { computeProgressPercent, formatProgressFraction } from '@/utils/progress'

const route = useRoute()
const tmdbId = computed(() => parseInt(route.params.id))
const seasonNumber = computed(() => parseInt(route.params.seasonNumber))
const auth = useAuthStore()
const season = ref(null)
const loading = ref(true)
const showName = ref('TV Show')
const watchedEps = ref(new Set())
const watchedAtMap = ref(new Map())
const {
  showDatePicker,
  pickerInitialValue,
  pickWatchedDateTime,
  handleDatePickerConfirm,
  handleDatePickerCancel,
} = useWatchedDateTimePicker()

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
  return watchedEps.value.has(epNum)
}

function getEpisodeWatchedAt(epNum) {
  return watchedAtMap.value.get(epNum) || ''
}

async function toggleEpisodeWatched(epNum) {
  const sn = seasonNumber.value
  if (watchedEps.value.has(epNum)) {
    watchedEps.value.delete(epNum)
    watchedAtMap.value.delete(epNum)
    await trackingAPI.unmarkEpisodeWatched({ tmdb_id: tmdbId.value, season_number: sn, episode_number: epNum })
  } else {
    watchedEps.value.add(epNum)
    await trackingAPI.markEpisodeWatched({ tmdb_id: tmdbId.value, season_number: sn, episode_number: epNum })
    watchedAtMap.value.set(epNum, new Date().toISOString())
  }
}

async function handleEpisodeWatchOption(payload) {
  const epNum = payload.episodeNumber
  const option = payload.option
  const sn = seasonNumber.value

  if (option === 'now') {
    await toggleEpisodeWatched(epNum)
    return
  }

  let watchedAtValue = null
  if (option === 'release') {
    if (payload.releaseDate) {
      watchedAtValue = `${payload.releaseDate}T00:00:00Z`
    }
  } else if (option === 'date') {
    watchedAtValue = await pickWatchedDateTime(getEpisodeWatchedAt(epNum))
    if (!watchedAtValue) return
  }

  if (watchedEps.value.has(epNum)) {
    watchedEps.value.delete(epNum)
    watchedAtMap.value.delete(epNum)
    await trackingAPI.unmarkEpisodeWatched({ tmdb_id: tmdbId.value, season_number: sn, episode_number: epNum })
  } else {
    watchedEps.value.add(epNum)
    await trackingAPI.markEpisodeWatched({
      tmdb_id: tmdbId.value,
      season_number: sn,
      episode_number: epNum,
      watched_at: watchedAtValue,
    })
    watchedAtMap.value.set(epNum, watchedAtValue || new Date().toISOString())
  }
}

async function handleSeasonWatchOption(option) {
  if (option === 'now') {
    // Just now - mark season as watched immediately
    try {
      await trackingAPI.markSeasonWatched({
        tmdb_id: tmdbId.value,
        season_number: seasonNumber.value
      })
      // Refresh watched episodes
      const res = await trackingAPI.getWatchedEpisodes(tmdbId.value)
      watchedEps.value = new Set(
        res.episodes
          .filter(e => e.season_number === seasonNumber.value)
          .map(e => e.episode_number)
      )
      watchedAtMap.value = new Map(
        res.episodes
          .filter(e => e.season_number === seasonNumber.value)
          .map(e => [e.episode_number, e.watched_at || ''])
      )
    } catch (e) {
      console.error('Failed to mark season:', e)
    }
    return
  }
  
  let watchedAt = null
  let useReleaseDate = false
  
  if (option === 'release') {
    useReleaseDate = true
  } else if (option === 'date') {
    watchedAt = await pickWatchedDateTime('')
    if (!watchedAt) {
      return
    }
  }
  
  try {
    await trackingAPI.markSeasonWatched({
      tmdb_id: tmdbId.value,
      season_number: seasonNumber.value,
      watched_at: watchedAt,
      use_release_date: useReleaseDate
    })
    // Refresh watched episodes
    const res = await trackingAPI.getWatchedEpisodes(tmdbId.value)
    watchedEps.value = new Set(
      res.episodes
        .filter(e => e.season_number === seasonNumber.value)
        .map(e => e.episode_number)
    )
    watchedAtMap.value = new Map(
      res.episodes
        .filter(e => e.season_number === seasonNumber.value)
        .map(e => [e.episode_number, e.watched_at || ''])
    )
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
    try {
      const data = await trackingAPI.getWatchedEpisodes(tmdbId.value)
      if (data?.episodes) {
        const sn = seasonNumber.value
        watchedEps.value = new Set(
          data.episodes
            .filter(e => e.season_number === sn)
            .map(e => e.episode_number)
        )
        watchedAtMap.value = new Map(
          data.episodes
            .filter(e => e.season_number === sn)
            .map(e => [e.episode_number, e.watched_at || ''])
        )
      }
    } catch (e) {
      console.error('Failed to load watched episodes:', e)
    }
  }
})
</script>
