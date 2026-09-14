<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
      <div class="flex flex-col md:flex-row gap-8">
        <div class="flex-shrink-0 w-full md:w-80">
          <SpoilerBlock :item-key="`episode-image-${tmdbId}-${seasonNum}-${episodeNum}`" :watched="isWatched" class="w-full aspect-video rounded-lg bg-surface-200 overflow-hidden">
            <img v-if="episodeData.still_path" :src="tmdbImageUrl(episodeData.still_path) || ''" :alt="episodeData.name" class="w-full h-full object-cover" />
            <div v-else class="w-full h-full flex items-center justify-center text-gray-600 text-4xl">{{ episodeData.episode_number }}</div>
          </SpoilerBlock>
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-3 mb-2 flex-wrap">
            <EpisodeCodePill
              :season-number="seasonNum"
              :episode-number="episodeNum"
              variant="plain"
              class="text-brand-500 font-mono text-xl"
            />
            <EpisodeTypePill :value="episodeData?.episode_type || ''" />
          </div>

          <h1 class="font-display text-3xl md:text-4xl text-primary font-semibold mb-3">{{ episodeData.name }}</h1>

          <div class="text-sm text-muted mb-4">
            <span v-if="episodeData.air_date">{{ formatDateTimeByLocale(episodeData.air_date) }}</span>
            <span v-if="episodeData.air_date && episodeData.runtime"> · </span>
            <span v-if="episodeData.runtime">{{ episodeData.runtime }} min</span>
            <span v-if="showData?.name"> · {{ showData.name }} S{{ seasonNum }}</span>
          </div>
          <div v-if="episodeData.vote_average" class="flex items-center gap-1 mb-4">
            <RatingBadge :value="formatRating(episodeData.vote_average)" :votes="episodeData.vote_count || 0" out-of-ten />
          </div>

          <div class="flex flex-wrap items-center gap-2 mb-4">
            <WatchSplitButton
              :active="isWatched"
              :label="isWatched ? 'Watched' : 'Watch'"
              :release-date="episodeData?.air_date ?? ''"
              :title-text="watchButtonTooltip"
              @trigger="handleWatchTrigger"
              @select="handleWatchOption"
            />
            <ExternalLinks
              :tmdb-url="externalLinks.tmdbUrl"
              :tvmaze-url="externalLinks.tvmazeUrl"
              :imdb-url="externalLinks.imdbUrl"
            />
          </div>

          <SpoilerBlock v-if="episodeData.overview" :item-key="`episode-overview-${tmdbId}-${seasonNum}-${episodeNum}`" :watched="isWatched" class="w-full max-w-2xl">
            <p class="text-secondary text-sm leading-relaxed">{{ episodeData.overview }}</p>
          </SpoilerBlock>
        </div>
      </div>

      <div class="grid md:grid-cols-3 gap-8 mt-10">
        <div class="md:col-span-2 space-y-8">
          <div v-if="episodeCast.length">
            <h3 class="text-primary font-medium mb-3">Cast</h3>
            <CastGrid :people="episodeCast" />
          </div>
          <div v-if="creditsData?.guest_stars?.length">
            <h3 class="text-primary font-medium mb-3">Guest stars</h3>
            <CastGrid :people="creditsData.guest_stars" empty-label="No guest stars listed." />
          </div>
        </div>
        <div>
          <div v-if="episodeCrew.length" class="card p-4">
            <p class="text-xs text-gray-500 uppercase tracking-wider mb-2">Crew</p>
            <div class="space-y-1.5 text-sm">
              <div v-for="person in episodeCrew.slice(0, 8)" :key="person.credit_id" class="text-muted">
                <span class="text-gray-500">{{ person.job }}:</span> <span class="text-secondary">{{ person.name }}</span>
              </div>
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

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { trackingAPI, mediaAPI } from '@/api'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'
import EpisodeTypePill from '@/components/EpisodeTypePill.vue'
import WatchSplitButton from '@/components/WatchSplitButton.vue'
import SpoilerBlock from '@/components/SpoilerBlock.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import EpisodeUnwatchDialog from '@/components/EpisodeUnwatchDialog.vue'
import ExternalLinks from '@/components/ExternalLinks.vue'
import CastGrid from '@/components/CastGrid.vue'
import { formatDateTimeByLocale, useI18n } from '@/i18n'
import { useEpisodeWatchActions } from '@/composables/useEpisodeWatchActions'
import { tmdbImageUrl } from '@/utils/images'
import { episodeExternalLinks } from '@/utils/externalLinks'
import { watchedTooltipText } from '@/utils/watchOptions'
import type { Credits, Episode, TVShow, WatchedEpisode } from '@/types/api'
import type { WatchedAtOption } from '@/utils/watchOptions'

const route = useRoute()

const tmdbId = computed(() => Number.parseInt(String(route.params.id), 10) || 0)
const seasonNum = computed(() => Number.parseInt(String(route.params.seasonNumber), 10) || 0)
const episodeNum = computed(() => Number.parseInt(String(route.params.episodeNumber), 10) || 0)

const backLink = computed(() => `/tv/${tmdbId.value}/season/${seasonNum.value}?tab=episodes`)

const loading = ref(true)
const showData = ref<TVShow | null>(null)
const episodeData = ref<Episode | null>(null)
const creditsData = ref<Credits | null>(null)
const isWatched = ref(false)
const watchedAt = ref('')
const unwatchDialog = ref<InstanceType<typeof EpisodeUnwatchDialog> | null>(null)
const {
  showDatePicker,
  pickerInitialValue,
  handleDatePickerConfirm,
  handleDatePickerCancel,
  markFromOption,
} = useEpisodeWatchActions()
const { t } = useI18n()

const watchButtonTooltip = computed(() => watchedTooltipText(isWatched.value, watchedAt.value, t))

const externalLinks = computed(() => episodeExternalLinks(tmdbId.value, seasonNum.value, episodeNum.value))

const episodeCast = computed(() => episodeData.value?.cast || creditsData.value?.cast || [])
const episodeCrew = computed(() => episodeData.value?.crew || creditsData.value?.crew || [])

function formatRating(rating: number) {
  if (!rating) return '0.0'
  return rating.toFixed(1)
}

async function load() {
  loading.value = true
  try {
    const [showRes, seasonRes, creditsRes, watchedRes] = await Promise.all([
      mediaAPI.getTV(tmdbId.value),
      mediaAPI.getSeason(tmdbId.value, seasonNum.value),
      mediaAPI.getEpisodeCredits(tmdbId.value, seasonNum.value, episodeNum.value).catch(() => null),
      trackingAPI.getWatchedEpisodes(tmdbId.value)
    ])

    showData.value = showRes
    creditsData.value = creditsRes
    const ep = seasonRes.episodes.find((episode) => episode.episode_number === episodeNum.value)
    if (ep) episodeData.value = ep

    const watchedEpisode = watchedRes.episodes.find(
      (episode: WatchedEpisode) => episode.season_number === seasonNum.value && episode.episode_number === episodeNum.value
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

async function handleWatchTrigger() {
  if (isWatched.value) {
    openUnwatchConfirm()
    return
  }
  await handleWatchOption('now')
}

async function handleWatchOption(option: WatchedAtOption) {
  const finalWatchedAt = await markFromOption(option, {
    tmdbId: tmdbId.value,
    seasonNumber: seasonNum.value,
    episodeNumber: episodeNum.value,
  }, { releaseDate: episodeData.value?.broadcast_start || episodeData.value?.air_date || '', pickerInitial: watchedAt.value })
  if (!finalWatchedAt) return
  isWatched.value = true
  watchedAt.value = finalWatchedAt
}

onMounted(load)
</script>
