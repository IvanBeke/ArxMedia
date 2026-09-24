<template>
  <div v-if="episodes?.length" class="divide-y divide-surface-200">
    <div
      v-for="ep in episodes"
      :key="ep.id || `${seasonNumber}-${ep.episode_number}`"
      class="episode-row grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-4 gap-y-3 py-4 first:pt-0 group md:flex md:gap-4"
    >
      <div class="episode-controls flex flex-row items-center gap-2 md:flex-col md:pt-4">
        <WatchCheckmarkMenu
          :watched="isEpisodeWatched(ep.episode_number)"
          :watched-at="getEpisodeWatchedAt(ep.episode_number)"
          :release-date="ep.broadcast_start || ep.air_date || ''"
          @select="(option) => emitWatchOption(ep, option)"
          @unwatch="emitUnwatch(ep)"
        />
        <span class="text-muted text-xs font-mono w-6 text-center">{{ String(ep.episode_number).padStart(2, '0') }}</span>
      </div>

      <div class="episode-thumbnail relative self-start w-full max-w-64 aspect-video overflow-hidden rounded-md bg-surface-200 md:max-w-none md:w-40 md:flex-shrink-0">
        <RouterLink :to="`/tv/${tmdbId}/season/${seasonNumber}/episode/${ep.episode_number}`" class="block h-full w-full">
          <img
            v-if="ep.still_path"
            :src="tmdbImageUrl(ep.still_path ?? '') || ''"
            :alt="ep.name"
            class="w-full h-full object-cover"
            loading="lazy"
          />
          <div v-else class="w-full h-full flex items-center justify-center text-gray-600 text-xl">
            {{ ep.episode_number }}
          </div>
        </RouterLink>
        <EpisodeTypePill
          :value="ep.episode_type"
          size="s"
          class="pointer-events-none absolute top-2 left-2 z-10 shadow ring-1 ring-black/10"
        />
      </div>

      <div class="episode-details col-span-2 min-w-0 md:col-auto md:flex-1 md:pt-1">
        <RouterLink :to="`/tv/${tmdbId}/season/${seasonNumber}/episode/${ep.episode_number}`" class="text-primary text-sm font-medium hover:text-brand-400 transition-colors">
          {{ ep.name }}
        </RouterLink>
        <p v-if="ep.overview" class="text-muted text-xs mt-1.5 line-clamp-3">{{ ep.overview }}</p>
        <div class="episode-meta mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted">
          <span v-if="ep.air_date">{{ formatDateTimeByLocale(ep.air_date) }}</span>
          <span v-if="ep.runtime">{{ ep.runtime }} min</span>
          <RatingBadge v-if="ep.vote_average" :value="ep.vote_average" size="xs" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import WatchCheckmarkMenu from '@/components/WatchCheckmarkMenu.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import EpisodeTypePill from '@/components/EpisodeTypePill.vue'
import { formatDateTimeByLocale } from '@/i18n'
import { tmdbImageUrl } from '@/utils/images'
import type { Episode } from '@/types/api'

type WatchMenuOption = 'now' | 'release' | 'unknown' | 'date'
type EpisodeWatchOption = { episodeNumber: number; option: WatchMenuOption; releaseDate: string | null }
type EpisodeUnwatch = { episodeNumber: number }

const props = withDefaults(defineProps<{
  episodes?: Episode[]
  tmdbId: number
  seasonNumber: number
  isEpisodeWatched: (episodeNumber: number) => boolean
  getEpisodeWatchedAt: (episodeNumber: number) => string
}>(), { episodes: () => [] })

const emit = defineEmits<{ 'watch-option': [payload: EpisodeWatchOption]; unwatch: [payload: EpisodeUnwatch] }>()

function emitWatchOption(episode: Episode, option: WatchMenuOption) {
  emit('watch-option', {
    episodeNumber: episode.episode_number,
    option,
    releaseDate: episode.broadcast_start || episode.air_date || null,
  })
}

function emitUnwatch(episode: Episode) {
  emit('unwatch', { episodeNumber: episode.episode_number })
}
</script>
