<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this episode?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <EpisodeUnwatchDialog ref="unwatchDialog" @unwatched="onEpisodeUnwatched" />

    <RouterLink :to="backLink" class="text-muted text-sm hover:text-brand-400 transition inline-flex items-center gap-1 mb-6">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
      Back to {{ showData?.name || 'Show' }} - Season {{ seasonNum }}
    </RouterLink>

    <div v-if="loading" class="space-y-4">
      <div class="h-8 w-64 skeleton rounded-md"></div>
      <div class="h-48 w-full skeleton rounded-lg"></div>
      <div class="h-20 w-full skeleton rounded-md"></div>
    </div>

      <div v-else-if="episodeData">
<div class="flex items-center gap-3 mb-4">
        <EpisodeCodePill
          :season-number="seasonNum"
          :episode-number="episodeNum"
          variant="plain"
          class="text-brand-500 font-mono text-xl"
        />
        <button
          v-if="isWatched"
          type="button"
          class="cursor-pointer bg-brand-500 hover:bg-brand-600 text-white px-3 py-1 rounded-md text-sm font-medium transition-colors"
          :title="watchButtonTooltip"
          @click="openUnwatchConfirm"
        >
          Watched
        </button>
        <WatchMenu
          v-else
          :release-date="episodeData?.air_date"
          @select="handleWatchOption"
        >
          <button
            class="bg-surface-200 text-muted hover:text-primary hover:bg-surface-300 px-3 py-1 rounded-md text-sm font-medium transition-colors"
            :title="watchButtonTooltip"
          >
            Mark watched
          </button>
        </WatchMenu>
      </div>

      <h1 class="font-display text-3xl text-primary font-semibold mb-6">{{ episodeData.name }}</h1>

      <div class="flex flex-col md:flex-row gap-6">
        <SpoilerBlock :item-key="`episode-image-${tmdbId}-${seasonNum}-${episodeNum}`" :watched="isWatched" class="w-full md:w-80 aspect-video rounded-lg bg-surface-200 overflow-hidden flex-shrink-0">
          <img v-if="episodeData.still_path" :src="tmdbImageUrl(episodeData.still_path)" :alt="episodeData.name" class="w-full h-full object-cover" />
          <div v-else class="w-full h-full flex items-center justify-center text-gray-600 text-4xl">{{ episodeData.episode_number }}</div>
        </SpoilerBlock>

        <div class="flex-1 space-y-4">
          <div class="text-sm text-muted">
            <span v-if="episodeData.air_date">{{ formatDate(episodeData.air_date) }}</span>
            <span v-if="episodeData.air_date && episodeData.runtime"> · </span>
            <span v-if="episodeData.runtime">{{ episodeData.runtime }} min</span>
            <div v-if="episodeData.vote_average" class="flex items-center gap-1 mt-2">
              <RatingBadge :value="formatRating(episodeData.vote_average)" :votes="episodeData.vote_count || 0" out-of-ten />
            </div>
            <div class="mt-2">
              <EpisodeTypePill :value="episodeData?.episode_type || ''" />
            </div>
          </div>

          <SpoilerBlock v-if="episodeData.overview" :item-key="`episode-overview-${tmdbId}-${seasonNum}-${episodeNum}`" :watched="isWatched" class="w-full">
            <p class="text-secondary text-sm leading-relaxed">{{ episodeData.overview }}</p>
          </SpoilerBlock>

          <div v-if="creditsData?.crew?.length" class="pt-4">
            <p class="text-gray-500 text-xs mb-2">Crew</p>
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <div v-for="person in creditsData.crew.slice(0, 8)" :key="person.credit_id" class="text-muted">
                <span class="text-gray-500">{{ person.job }}:</span> {{ person.name }}
              </div>
            </div>
          </div>
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

      <div v-if="creditsData?.guest_stars?.length" class="mt-6">
        <p class="text-gray-500 text-xs mb-2">Guest stars</p>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 text-sm">
          <div v-for="star in creditsData.guest_stars" :key="star.credit_id" class="flex items-center gap-3">
            <img v-if="star.profile_path" :src="tmdbImageUrl(star.profile_path, 'w92')" :alt="star.name" class="w-12 h-12 rounded-md object-cover" />
            <div v-else class="w-12 h-12 rounded-md bg-surface-200"></div>
            <div class="min-w-0">
              <p class="text-secondary">{{ star.name }}</p>
              <p class="text-gray-500">{{ star.character }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-16 text-gray-500">
      <p>Episode not found.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { trackingAPI, mediaAPI } from '@/api'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'
import EpisodeTypePill from '@/components/EpisodeTypePill.vue'
import WatchMenu from '@/components/WatchMenu.vue'
import SpoilerBlock from '@/components/SpoilerBlock.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import { formatDateByLocale, useI18n } from '@/i18n'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { tmdbImageUrl } from '@/utils/images'
import { watchedTooltipText } from '@/utils/watchOptions'

const route = useRoute()

const tmdbId = computed(() => parseInt(route.params.id) || 0)
const seasonNum = computed(() => parseInt(route.params.seasonNumber) || 0)
const episodeNum = computed(() => parseInt(route.params.episodeNumber) || 0)

const backLink = computed(() => `/tv/${tmdbId.value}/season/${seasonNum.value}`)

const loading = ref(true)
const showData = ref(null)
const episodeData = ref(null)
const creditsData = ref(null)
const isWatched = ref(false)
const watchedAt = ref('')
const unwatchDialog = ref(null)
const {
  showDatePicker,
  pickerInitialValue,
  handleDatePickerConfirm,
  handleDatePickerCancel,
  markFromOption,
} = useEpisodeWatchActions()
const { t } = useI18n()

const watchButtonTooltip = computed(() => watchedTooltipText(isWatched.value, watchedAt.value, t))

function formatRating(rating) {
  if (!rating) return '0.0'
  return rating.toFixed(1)
}

function formatDate(dateStr) {
  return formatDateByLocale(dateStr)
}

async function load() {
  loading.value = true
  try {
    const [showRes, seasonRes, creditsRes, watchedRes] = await Promise.all([
      mediaAPI.getTV(tmdbId.value),
      mediaAPI.getSeason(tmdbId.value, seasonNum.value),
      mediaAPI.getEpisodeCredits(tmdbId.value, seasonNum.value, episodeNum.value),
      trackingAPI.getWatchedEpisodes(tmdbId.value)
    ])

    showData.value = showRes
    creditsData.value = creditsRes
    const ep = seasonRes.episodes?.find(e => e.episode_number === episodeNum.value)
    if (ep) episodeData.value = ep

    const watchedEpisode = watchedRes.episodes?.find(
      e => e.season_number === seasonNum.value && e.episode_number === episodeNum.value
    )
    isWatched.value = Boolean(watchedEpisode)
    watchedAt.value = watchedEpisode?.watched_at || ''
  } catch (e) {
    console.error('Failed to load episode:', e)
  } finally {
    loading.value = false
  }
}

function openUnwatchConfirm() {
  unwatchDialog.value?.open({
    tmdbId: tmdbId.value,
    seasonNumber: seasonNum.value,
    episodeNumber: episodeNum.value,
  })
}

function onEpisodeUnwatched() {
  isWatched.value = false
  watchedAt.value = ''
}

async function handleWatchOption(option) {
  const finalWatchedAt = await markFromOption(option, {
    tmdbId: tmdbId.value,
    seasonNumber: seasonNum.value,
    episodeNumber: episodeNum.value,
  }, { releaseDate: episodeData.value?.air_date || '', pickerInitial: watchedAt.value })
  if (!finalWatchedAt) return
  isWatched.value = true
  watchedAt.value = finalWatchedAt
}

onMounted(load)
</script>
