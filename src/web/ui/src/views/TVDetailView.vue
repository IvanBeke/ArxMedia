<template>
  <div>
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this episode?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <div class="relative h-72 md:h-[28rem]">
      <img v-if="show?.backdrop_url" :src="show.backdrop_url" class="w-full h-full object-cover" />
      <div class="absolute inset-0 bg-gradient-to-t from-surface via-surface/60 to-transparent"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-surface/80 to-transparent"></div>
    </div>

    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-20 relative z-10 pb-20">
      <div class="flex flex-col md:flex-row gap-8">
        <div class="flex-shrink-0">
          <div class="w-36 md:w-48 rounded-md overflow-hidden shadow-2xl border border-surface-200">
            <img v-if="show?.poster_url" :src="show.poster_url" :alt="show?.name" class="w-full" />
            <div v-else class="aspect-[2/3] bg-surface-200 flex flex-col items-center justify-center text-gray-500 p-4">
              <svg class="w-12 h-12 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M15 10l4.553-2.069A1 1 0 0121 8.876V15.5a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z"/>
              </svg>
              <span class="text-xs text-center">{{ show?.name }}</span>
            </div>
          </div>
        </div>

        <div class="flex-1 pt-2">
          <div v-if="loading" class="space-y-3">
            <div class="h-10 w-3/4 skeleton rounded-md"></div>
            <div class="h-4 w-1/2 skeleton rounded-md"></div>
            <div class="h-20 skeleton rounded-md"></div>
          </div>

          <template v-else-if="show">
            <div class="flex flex-wrap gap-2 mb-3">
              <span v-for="g in show.genres" :key="g.id" class="badge bg-surface-200 text-secondary text-xs">{{ g.name }}</span>
            </div>

            <h1 class="font-display text-3xl md:text-5xl text-primary font-semibold mb-1">{{ show.name }}</h1>
            <p class="text-muted text-sm mb-4">{{ show.first_air_date ? new Date(show.first_air_date).getFullYear() : '' }} · {{ show.number_of_seasons }} Season{{ show.number_of_seasons !== 1 ? 's' : '' }} · {{ show.number_of_episodes }} Episode{{ show.number_of_episodes !== 1 ? 's' : '' }}</p>

            <div class="flex items-center gap-4 mb-4 text-sm">
              <RatingBadge :value="show.vote_average" :votes="show.vote_count" out-of-ten />
            </div>

            <p v-if="show.networks" class="text-muted text-sm mb-3">{{ show.networks }}</p>
            <p class="text-secondary leading-relaxed mb-6 max-w-2xl">{{ show.overview }}</p>

            <div v-if="show.watch_providers" class="mb-6">
              <p class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Watch Now ({{ show.watch_providers.region }})</p>
              <div class="flex flex-wrap gap-2">
                <a
                  v-for="p in (show.watch_providers.flatrate || []).slice(0, 6)"
                  :key="`provider-${p.provider_id}`"
                  :href="show.watch_providers.link || '#'
                  "
                  target="_blank"
                  rel="noopener noreferrer"
                  class="badge bg-surface-200 text-secondary hover:text-primary"
                >
                  {{ p.provider_name }}
                </a>
                <span v-if="!(show.watch_providers.flatrate || []).length" class="text-xs text-muted">No streaming providers found.</span>
              </div>
            </div>

            <div v-if="auth.isAuthenticated" class="flex flex-wrap gap-2 mb-4">
              <div class="relative" ref="statusMenuRef">
                <button @click="toggleStatusMenu" class="btn-primary flex items-center gap-2 text-sm">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                  {{ watchButtonLabel }}
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>

                <div
                  v-if="statusMenuOpen"
                  class="absolute left-0 mt-1 min-w-[210px] bg-surface border border-surface-200 rounded-md shadow-lg z-50"
                >
                  <button
                    v-if="showStatus === WATCH_ENTRY_STATUS.WATCHING || showStatus === WATCH_ENTRY_STATUS.WATCHED"
                    type="button"
                    @click="handleRemoveWatchedEpisodes"
                    class="block w-full px-3 py-2 text-left text-sm text-muted hover:bg-surface-200 hover:text-primary transition-colors"
                  >
                    Remove watched episodes
                  </button>
                  <button
                    v-if="showStatus === WATCH_ENTRY_STATUS.WATCHING || showStatus === WATCH_ENTRY_STATUS.WATCHED"
                    type="button"
                    @click="handleDropShow"
                    class="block w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-surface-200 hover:text-red-300 transition-colors"
                  >
                    Drop show
                  </button>
                  <button
                    v-if="showStatus !== WATCH_ENTRY_STATUS.WATCHING && showStatus !== WATCH_ENTRY_STATUS.WATCHED"
                    type="button"
                    @click="handleWatchingAction"
                    class="block w-full px-3 py-2 text-left text-sm text-muted hover:bg-surface-200 hover:text-primary transition-colors"
                  >
                    Set as watching
                  </button>
                </div>
              </div>
              <button v-if="showStatus !== WATCH_ENTRY_STATUS.WATCHING && !hasWatchedEpisodes" @click="handleWatchlistAction" class="btn-ghost flex items-center gap-2 text-sm">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                </svg>
                {{ showStatus === 'watchlist' ? 'In Watchlist' : 'Watchlist' }}
              </button>
            </div>

            <div v-if="auth.isAuthenticated" class="mb-4">
              <p class="text-xs text-gray-500 mb-1.5 uppercase tracking-wider">Your Rating</p>
              <StarRating v-model="userRating" @update:modelValue="submitRating" />
            </div>

            <div v-if="successMsg" class="mb-4 px-3 py-1.5 bg-green-500/10 border border-green-500/20 text-green-400 rounded-md text-sm inline-block">
              {{ successMsg }}
            </div>
            <div v-if="errorMsg" class="mb-4 px-3 py-1.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm inline-block">
              {{ errorMsg }}
            </div>
          </template>
        </div>
      </div>

      <div class="mt-10 border-b border-surface-200">
        <nav class="flex gap-6">
          <button @click="activeTab = 'seasons'" class="pb-3 text-sm font-medium" :class="activeTab === 'seasons' ? 'tab-active' : 'tab-inactive'">
            Seasons
          </button>
          <button @click="activeTab = 'overview'" class="pb-3 text-sm font-medium" :class="activeTab === 'overview' ? 'tab-active' : 'tab-inactive'">
            Overview
          </button>
        </nav>
      </div>

      <div class="mt-6">
        <template v-if="activeTab === 'seasons'">
          <div v-if="loadingSeasons" class="space-y-4">
            <div v-for="n in 3" :key="n" class="h-20 skeleton rounded-lg"></div>
          </div>

          <div v-else-if="show?.seasons?.length" class="space-y-2">
            <div v-for="season in show.seasons" :key="season.season_number" class="card">
              <div class="w-full flex items-center gap-4 p-4">
                <div class="w-12 h-16 rounded-md bg-surface-200 overflow-hidden flex-shrink-0 cursor-pointer" @click="toggleSeason(season.season_number)">
                  <img v-if="season.poster_url" :src="season.poster_url" :alt="season.name" class="w-full h-full object-cover" />
                  <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-500 p-1">
                    <span class="text-xs font-bold">S{{ season.season_number }}</span>
                  </div>
                </div>

                <div class="flex-1 min-w-0">
                  <div class="flex items-center justify-between">
                    <RouterLink :to="`/tv/${tmdbId}/season/${season.season_number}`" class="text-primary font-medium hover:text-brand-400 transition-colors">
                      {{ season.name }}
                    </RouterLink>
                    <div class="flex items-center gap-2">
                      <button @click.stop="toggleSeasonWatched(season.season_number)" class="text-xs px-2.5 py-1 rounded-md font-medium transition-colors" :class="getSeasonProgress(season.season_number) === 100 ? 'bg-brand-500 text-white hover:bg-brand-600' : 'bg-surface-200 text-muted hover:text-primary hover:bg-surface-300'">
                        {{ getSeasonProgress(season.season_number) === 100 ? 'Watched' : 'Mark watched' }}
                      </button>
                      <button @click="toggleSeason(season.season_number)" class="p-1 hover:bg-surface-200 rounded transition-colors">
                        <svg class="w-5 h-5 text-muted transition-transform" :class="expandedSeason === season.season_number ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                  <p class="text-muted text-sm mt-0.5">{{ season.episode_count }} episodes{{ season.air_date ? ` · ${new Date(season.air_date).getFullYear()}` : '' }}</p>
                  <div class="mt-2">
                    <ProgressBar :pct="getSeasonProgress(season.season_number)" />
                    <p class="text-xs text-muted mt-1">{{ getSeasonProgress(season.season_number) }}% watched</p>
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
                  :get-episode-watched-at="(episodeNumber) => getEpisodeWatchedAt(season.season_number, episodeNumber)"
                  @watch-option="(payload) => handleEpisodeWatchOption(season.season_number, payload)"
                />

                <div v-else class="p-4 text-center text-muted text-sm">No episodes available for this season.</div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'overview'">
          <div class="grid md:grid-cols-3 gap-8">
            <div class="md:col-span-2">
              <h3 class="text-primary font-medium mb-3">Synopsis</h3>
              <p class="text-secondary leading-relaxed">{{ show?.overview }}</p>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { onClickOutside } from '@vueuse/core'
import { mediaAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import StarRating from '@/components/StarRating.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import SpoilerBlock from '@/components/SpoilerBlock.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import { MEDIA_TYPE, WATCH_ENTRY_MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { formatDateByLocale } from '@/i18n'
import { getApiErrorMessage } from '@/utils/errors'
import { useWatchlistQuickActions } from '@/composables/useWatchlistQuickActions'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'

const route = useRoute()
const auth = useAuthStore()
const tmdbId = computed(() => parseInt(route.params.id))

const show = ref(null)
const loading = ref(true)
const loadingSeasons = ref(false)
const userRating = ref(0)
const showStatus = ref('none')
const successMsg = ref('')
const errorMsg = ref('')

const activeTab = ref('seasons')
const expandedSeason = ref(null)
const seasonEpisodes = ref({})
const seasonLoading = ref(null)
const watchedEps = ref(new Set())
const watchedAtMap = ref(new Map())
const hasWatchedEpisodes = computed(() => watchedEps.value.size > 0)
const {
  showDatePicker,
  pickerInitialValue,
  pickWatchedDateTime,
  handleDatePickerConfirm,
  handleDatePickerCancel,
} = useWatchedDateTimePicker()

const {
  addToWatchlist,
  removeFromWatchlist,
} = useWatchlistQuickActions()

const statusMenuOpen = ref(false)
const statusMenuRef = ref(null)

const watchButtonLabel = computed(() => {
  if (showStatus.value === WATCH_ENTRY_STATUS.WATCHING) return 'Watching'
  if (showStatus.value === WATCH_ENTRY_STATUS.WATCHED) return 'Watched'
  if (showStatus.value === WATCH_ENTRY_STATUS.DROPPED) return 'Dropped'
  if (showStatus.value === 'watchlist') return 'Watchlist'
  return 'Watch'
})

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
  showStatus.value = 'none'
}

onClickOutside(statusMenuRef, () => {
  statusMenuOpen.value = false
})

function imgUrl(path, size = 'w185') {
  return path ? `https://image.tmdb.org/t/p/${size}${path}` : null
}

function showSuccess(msg) {
  errorMsg.value = ''
  successMsg.value = msg
  setTimeout(() => { successMsg.value = '' }, 2500)
}

function showError(msg) {
  successMsg.value = ''
  errorMsg.value = msg
  setTimeout(() => { errorMsg.value = '' }, 3500)
}

function toggleStatusMenu() {
  statusMenuOpen.value = !statusMenuOpen.value
}

function isWatched(sn, epNum) {
  return watchedEps.value.has(`${sn}-${epNum}`)
}

function getEpisodeWatchedAt(sn, epNum) {
  const key = `${sn}-${epNum}`
  return watchedAtMap.value.get(key) || ''
}

async function handleEpisodeWatchOption(sn, payload) {
  const epNum = payload.episodeNumber
  const option = payload.option

  if (option === 'now') {
    await markEpisode(sn, epNum)
    return
  }
  if (option === 'release') {
    let watchedAt = null
    if (payload.releaseDate) {
      watchedAt = `${payload.releaseDate}T00:00:00Z`
    }
    await markEpisode(sn, epNum, watchedAt)
    return
  }
  if (option === 'date') {
    const watchedAt = await pickWatchedDateTime('')
    if (watchedAt) {
      await markEpisode(sn, epNum, watchedAt)
    }
  }
}

async function markEpisode(sn, epNum, watchedAt) {
  const key = `${sn}-${epNum}`
  if (watchedEps.value.has(key)) {
    await trackingAPI.unmarkEpisodeWatched({ tmdb_id: tmdbId.value, season_number: sn, episode_number: epNum })
    watchedEps.value.delete(key)
    watchedAtMap.value.delete(key)
    showSuccess('Episode unwatched')
  } else {
    await trackingAPI.markEpisodeWatched({ tmdb_id: tmdbId.value, season_number: sn, episode_number: epNum, watched_at: watchedAt })
    watchedEps.value.add(key)
    watchedAtMap.value.set(key, watchedAt || new Date().toISOString())
    showSuccess('Episode marked as watched')
  }
  delete seasonEpisodes.value[sn]
  await loadWatchedEpisodes()
  await loadSeason(sn)
  await loadShow()
}

function toggleSeason(sn) {
  if (expandedSeason.value === sn) {
    expandedSeason.value = null
  } else {
    expandedSeason.value = sn
    loadSeason(sn)
  }
}

async function loadSeason(sn) {
  if (seasonEpisodes.value[sn]) return
  seasonLoading.value = sn
  try {
    const data = await mediaAPI.getSeason(tmdbId.value, sn)
    if (data) seasonEpisodes.value[sn] = data.episodes || []
  } catch (err) {
    seasonEpisodes.value[sn] = []
  } finally {
    seasonLoading.value = null
  }
}

function getSeasonProgress(sn) {
  const season = show.value?.seasons?.find(s => s.season_number === sn)
  const eps = seasonEpisodes.value[sn]
  let total = 0
  if (eps?.length) {
    total = eps.length
  } else if (season?.episode_count) {
    total = season.episode_count
  } else {
    total = Array.from(watchedEps.value).filter(k => k.startsWith(`${sn}-`)).length || 0
  }
  if (total === 0) return 0
  const watched = Array.from(watchedEps.value).filter(k => k.startsWith(`${sn}-`)).length
  return Math.round((watched / total) * 100)
}

async function toggleSeasonWatched(sn) {
  const progress = getSeasonProgress(sn)
  if (progress === 100) {
    await trackingAPI.unmarkSeasonWatched({ tmdb_id: tmdbId.value, season_number: sn })
    showSuccess('Season unwatched')
  } else {
    await trackingAPI.markSeasonWatched({ tmdb_id: tmdbId.value, season_number: sn })
    await setShowStatus(WATCH_ENTRY_STATUS.WATCHING)
    showSuccess('Season marked as watched')
  }
  delete seasonEpisodes.value[sn]
  await loadWatchedEpisodes()
  await loadSeason(sn)
  await loadShow()
  const savedExpanded = expandedSeason.value
  expandedSeason.value = null
  await nextTick()
  expandedSeason.value = savedExpanded === sn ? null : savedExpanded
}

async function loadWatchedEpisodes() {
  try {
    const data = await trackingAPI.getWatchedEpisodes(tmdbId.value)
    if (data?.episodes) {
      watchedEps.value = new Set(data.episodes.map(e => `${e.season_number}-${e.episode_number}`))
      watchedAtMap.value = new Map(
        data.episodes.map(e => [`${e.season_number}-${e.episode_number}`, e.watched_at || ''])
      )
    }
  } catch (err) {}
}

async function setShowStatus(status) {
  if (status === WATCH_ENTRY_STATUS.WATCHING && showStatus.value === 'watchlist') {
    await removeFromWatchlist(MEDIA_TYPE.TV, tmdbId.value)
  }
  if (status === 'watchlist' && showStatus.value === WATCH_ENTRY_STATUS.WATCHING) {
    await trackingAPI.removeFromHistory({ media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE, tmdb_id: tmdbId.value })
  }

  if (status === WATCH_ENTRY_STATUS.WATCHING) {
    // Show watching status is now determined by watching any episode
  } else if (status === 'watchlist') {
    await addToWatchlist(MEDIA_TYPE.TV, tmdbId.value)
  } else if (status === 'none') {
    await removeFromWatchlist(MEDIA_TYPE.TV, tmdbId.value)
  }
  
  showStatus.value = status
}

async function handleWatchingAction() {
  statusMenuOpen.value = false
  if (showStatus.value === WATCH_ENTRY_STATUS.WATCHING) {
    await setShowStatus('none')
    showSuccess('Removed from watching')
  } else {
    await setShowStatus(WATCH_ENTRY_STATUS.WATCHING)
    showSuccess('Added to watching!')
  }
}

async function handleRemoveWatchedEpisodes() {
  statusMenuOpen.value = false
  const data = await trackingAPI.getWatchedEpisodes(tmdbId.value)
  const episodes = (data?.episodes || []).filter(e => e.season_number > 0)
  await Promise.all(
    episodes.map((e) => trackingAPI.unmarkEpisodeWatched({
      tmdb_id: tmdbId.value,
      season_number: e.season_number,
      episode_number: e.episode_number,
    }))
  )
  watchedEps.value = new Set()
  watchedAtMap.value = new Map()
  seasonEpisodes.value = {}
  await loadShow()
  showSuccess('Removed watched episodes')
}

async function handleDropShow() {
  statusMenuOpen.value = false
  await trackingAPI.dropShow({ tmdb_id: tmdbId.value })
  watchedEps.value = new Set()
  watchedAtMap.value = new Map()
  seasonEpisodes.value = {}
  await loadShow()
  showSuccess('Show dropped')
}

async function handleWatchlistAction() {
  if (showStatus.value === 'watchlist') {
    await setShowStatus('none')
    showSuccess('Removed from watchlist')
  } else {
    try {
      await setShowStatus('watchlist')
      showSuccess('Added to watchlist!')
    } catch (error) {
      showError(getApiErrorMessage(error, 'Could not add to watchlist.'))
    }
  }
}

async function submitRating(score) {
  await trackingAPI.rate({ media_type: MEDIA_TYPE.TV, tmdb_id: tmdbId.value, score })
  showSuccess(`Rated ${score}/10!`)
}

async function loadShow() {
  try {
    const data = await mediaAPI.getTV(tmdbId.value)
    if (data) {
      show.value = data
      syncShowStatusFromUserStatus()
    }
  } catch (e) {}
}

onMounted(async () => {
  await loadShow()
  loading.value = false

  if (auth.isAuthenticated) {
    const [ratingRes, epsRes] = await Promise.allSettled([
      trackingAPI.getRatings({ media_type: MEDIA_TYPE.TV, tmdb_id: tmdbId.value }),
      trackingAPI.getWatchedEpisodes(tmdbId.value)
    ])

    if (epsRes.status === 'fulfilled' && epsRes.value?.episodes?.length) {
      watchedEps.value = new Set(
        epsRes.value.episodes.map(e => `${e.season_number}-${e.episode_number}`)
      )
      watchedAtMap.value = new Map(
        epsRes.value.episodes.map(e => [`${e.season_number}-${e.episode_number}`, e.watched_at || ''])
      )
    }
    
    if (ratingRes.status === 'fulfilled') {
      const ratings = ratingRes.value.results || ratingRes.value
      const found = ratings[0]
      if (found) userRating.value = found.score
    }
  }
})
</script>
