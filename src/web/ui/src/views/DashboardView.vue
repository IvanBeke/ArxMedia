<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="font-display text-2xl text-primary font-semibold mb-1">Dashboard</h1>
    <p class="text-muted text-sm mb-8">Welcome back, <span class="text-brand-400">{{ auth.user?.username }}</span></p>

    <!-- Weekly Pulse stats -->
    <div v-if="loadingStats" class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10">
      <div v-for="n in 4" :key="n" class="h-24 skeleton rounded-lg"></div>
    </div>

    <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10">
      <div class="card p-4">
        <p class="text-3xl font-display text-brand-500">{{ stats?.movies_watched || 0 }}</p>
        <p class="text-muted text-xs mt-1">Movies Watched</p>
      </div>
      <div class="card p-4">
        <p class="text-3xl font-display text-brand-500">{{ stats?.episodes_watched || 0 }}</p>
        <p class="text-muted text-xs mt-1">Episodes Watched</p>
      </div>
      <div class="card p-4">
        <p class="text-3xl font-display text-brand-500">{{ stats?.shows_watching || 0 }}</p>
        <p class="text-muted text-xs mt-1">Shows Watching</p>
      </div>
      <div class="card p-4">
        <p class="text-3xl font-display text-brand-500">{{ stats?.average_rating || '–' }}</p>
        <p class="text-muted text-xs mt-1">Avg. Rating</p>
      </div>
    </div>

    <!-- Up Next Row -->
    <div class="mb-8">
      <RouterLink to="/my-shows" class="section-title mb-4 inline-flex items-center gap-1.5 hover:text-brand-400 transition-colors">
        <span>Up Next</span>
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </RouterLink>
      <div v-if="loadingUpNext" class="flex gap-4">
        <div v-for="n in 3" :key="n" class="w-40 h-60 skeleton rounded-lg flex-shrink-0"></div>
      </div>
      <div v-else-if="upNext?.length" class="flex gap-4 overflow-x-auto pb-2">
        <div
          v-for="item in upNext"
          :key="item.tmdb_id"
          class="flex-shrink-0 w-[165px] md:w-[173px] xl:w-[189px]"
        >
          <FutureEpisodeCard
            :show-title="item.show_name"
            :episode-title="item.next_episode?.name || ''"
            :episode-type="item.next_episode?.episode_type || ''"
            :season-number="item.next_episode?.season_number || 0"
            :episode-number="item.next_episode?.episode_number || 0"
            :poster-url="item.poster_url"
            :poster-link-to="getUpNextPosterLink(item)"
            :title-link-to="`/tv/${item.tmdb_id}`"
            :show-new-badge="item.is_new"
            :show-watch-action="true"
            :watch-loading="markingId === item.tmdb_id"
            :progress-percent="item.progress_percent"
            :episode-duration-minutes="item.next_episode?.runtime"
            :episodes-left="item.episodes_left"
            :runtime-left-minutes="item.runtime_left_minutes"
            :runtime-left-has-unknown="item.runtime_left_has_unknown"
            @watch="markNextEpisodeWatched(item)"
          />
        </div>
      </div>
      <div v-else class="card p-6 text-center">
        <p class="text-muted text-sm">My Shows is empty. Add titles to Watchlist or start watching to see them here.</p>
      </div>
    </div>

    <!-- Upcoming Row -->
    <div class="mb-8">
      <RouterLink to="/calendar" class="section-title mb-4 inline-flex items-center gap-1.5 hover:text-brand-400 transition-colors">
        <span>Upcoming</span>
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </RouterLink>
      <div v-if="loadingUpcoming" class="flex gap-4">
        <div v-for="n in 3" :key="n" class="w-40 h-60 skeleton rounded-lg flex-shrink-0"></div>
      </div>
      <div v-else-if="upcoming?.length" class="flex gap-4 overflow-x-auto pb-2">
        <div
          v-for="item in upcoming"
          :key="`${item.tmdb_id}-${item.season_number}-${item.episode_number}`"
          class="flex-shrink-0 w-[165px] md:w-[173px] xl:w-[189px]"
        >
          <FutureEpisodeCard
            :show-title="item.show_name"
            :episode-title="item.name || ''"
            :episode-type="item.episode_type || ''"
            :season-number="item.season_number"
            :episode-number="item.episode_number"
            :poster-url="item.poster_url"
            :poster-link-to="getUpcomingPosterLink(item)"
            :title-link-to="`/tv/${item.tmdb_id}`"
            :meta-text="formatDate(item.air_date)"
          />
        </div>
      </div>
      <div v-else class="card p-6 text-center">
        <p class="text-muted text-sm">No upcoming episodes</p>
      </div>
    </div>

    <div class="mb-8">
      <RouterLink to="/history" class="section-title mb-4 inline-flex items-center gap-1.5 hover:text-brand-400 transition-colors">
        <span>Recent Activity</span>
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </RouterLink>
      <div v-if="loadingStats" class="space-y-2">
        <div v-for="n in 5" :key="n" class="h-14 skeleton rounded-lg"></div>
      </div>
      <div v-else-if="stats?.recent_activity?.length" class="flex gap-4 overflow-x-auto pb-2">
        <HistoryMediaCard
          v-for="entry in stats.recent_activity"
          :key="entry.id"
          :entry="entry"
          :link-to="getLink(entry)"
          :show-remove-action="true"
          :remove-loading="deletingEntryId === entry.id"
          :remove-confirm-text="getRemoveHistoryConfirmText(entry)"
          class="flex-shrink-0 w-[165px] md:w-[173px] xl:w-[189px]"
          @action:history-remove="removeRecentEntry"
        />
      </div>
      <div v-else class="card p-8 text-center">
        <p class="text-muted text-sm mb-3">No activity yet</p>
        <RouterLink to="/search" class="btn-primary text-sm">Discover Content</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { formatDateByLocale, useI18n } from '@/i18n'
import { MEDIA_TYPE, WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import FutureEpisodeCard from '@/components/FutureEpisodeCard.vue'
import { formatIsoAsDDMMYYYY } from '@/utils/temporal'

const auth = useAuthStore()
const { t } = useI18n()
const stats = ref(null)
const loadingStats = ref(true)
const upNext = ref(null)
const loadingUpNext = ref(true)
const upcoming = ref(null)
const loadingUpcoming = ref(true)
const markingId = ref(null)
const deletingEntryId = ref(null)

function formatDate(d) {
  if (!d) return ''
  return formatIsoAsDDMMYYYY(d) || formatDateByLocale(d)
}

function getLink(entry) {
  if (entry.media_type === MEDIA_TYPE.MOVIE) return `/movies/${entry.tmdb_id}`
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return `/tv/${entry.tmdb_id}/season/${entry.season_number}/episode/${entry.episode_number}`
  }
  return `/tv/${entry.tmdb_id}`
}

function getUpNextPosterLink(item) {
  return `/tv/${item.tmdb_id}/season/${item.next_episode?.season_number}/episode/${item.next_episode?.episode_number}`
}

function getUpcomingPosterLink(item) {
  return `/tv/${item.tmdb_id}/season/${item.season_number}/episode/${item.episode_number}`
}

function getRemoveHistoryConfirmText(entry) {
  if (entry?.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return t('remove_history_confirm_episode')
  }
  return t('remove_history_confirm_movie')
}

async function markNextEpisodeWatched(item) {
  if (!item.next_episode || markingId.value) return
  markingId.value = item.tmdb_id
  try {
    await trackingAPI.markEpisodeWatched({
      tmdb_id: item.tmdb_id,
      season_number: item.next_episode.season_number,
      episode_number: item.next_episode.episode_number
    })
    const [upNextRes, statsRes] = await Promise.all([
      trackingAPI.getUpNext(),
      trackingAPI.getStats(),
    ])
    upNext.value = upNextRes
    stats.value = statsRes
  } catch (e) {
    console.error('Failed to mark episode watched', e)
  } finally {
    markingId.value = null
  }
}

async function removeRecentEntry(entry) {
  if (deletingEntryId.value) return
  deletingEntryId.value = entry.id

  try {
    await trackingAPI.deleteHistory(entry.id)
    stats.value = await trackingAPI.getStats()
  } catch (e) {
    console.error('Failed to delete history entry', e)
  } finally {
    deletingEntryId.value = null
  }
}

onMounted(async () => {
  const [statsRes, upNextRes, upcomingRes] = await Promise.allSettled([
    trackingAPI.getStats(),
    trackingAPI.getUpNext(),
    trackingAPI.getUpcoming(),
  ])

  if (statsRes.status === 'fulfilled') {
    stats.value = statsRes.value
  } else {
    console.error('stats error:', statsRes.reason)
  }
  loadingStats.value = false

  if (upNextRes.status === 'fulfilled') {
    upNext.value = upNextRes.value
  } else {
    console.error('upNext error:', upNextRes.reason)
  }
  loadingUpNext.value = false

  if (upcomingRes.status === 'fulfilled') {
    upcoming.value = upcomingRes.value
  } else {
    console.error('upcoming error:', upcomingRes.reason)
  }
  loadingUpcoming.value = false
})
</script>
