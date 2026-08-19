<template>
  <div v-if="episodes?.length" class="divide-y divide-surface-200">
    <div
      v-for="ep in episodes"
      :key="ep.id || `${seasonNumber}-${ep.episode_number}`"
      class="flex gap-4 py-4 first:pt-0 group"
    >
      <div class="flex flex-col items-center gap-2 pt-4">
        <WatchCheckmarkMenu
          :watched="isEpisodeWatched(ep.episode_number)"
          :watched-at="getEpisodeWatchedAt(ep.episode_number)"
          :release-date="ep.air_date"
          @select="(option) => emitWatchOption(ep, option)"
        />
        <span class="text-muted text-xs font-mono w-6 text-center">{{ String(ep.episode_number).padStart(2, '0') }}</span>
      </div>

      <RouterLink :to="`/tv/${tmdbId}/season/${seasonNumber}/episode/${ep.episode_number}`" class="flex-shrink-0 w-32 sm:w-40 aspect-video rounded-md bg-surface-200 overflow-hidden mt-1 block">
        <img
          v-if="ep.still_path"
          :src="imgUrl(ep.still_path)"
          :alt="ep.name"
          class="w-full h-full object-cover"
          loading="lazy"
        />
        <div v-else class="w-full h-full flex items-center justify-center text-gray-600 text-xl">
          {{ ep.episode_number }}
        </div>
      </RouterLink>

      <div class="flex-1 min-w-0 pt-1">
        <RouterLink :to="`/tv/${tmdbId}/season/${seasonNumber}/episode/${ep.episode_number}`" class="text-primary text-sm font-medium hover:text-brand-400 transition-colors">
          {{ ep.name }}
        </RouterLink>
        <p v-if="ep.overview" class="text-muted text-xs mt-1.5 line-clamp-3">{{ ep.overview }}</p>
        <div class="flex items-center gap-3 mt-2 text-xs text-muted">
          <span v-if="ep.air_date">{{ formatDateByLocale(ep.air_date) }}</span>
          <span v-if="ep.runtime">· {{ ep.runtime }} min</span>
          <RatingBadge v-if="ep.vote_average" :value="ep.vote_average" size="xs" />
          <EpisodeTypePill :value="ep.episode_type" size="s" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import WatchCheckmarkMenu from '@/components/WatchCheckmarkMenu.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import EpisodeTypePill from '@/components/EpisodeTypePill.vue'
import { formatDateByLocale } from '@/i18n'

const props = defineProps({
  episodes: { type: Array, default: () => [] },
  tmdbId: { type: Number, required: true },
  seasonNumber: { type: Number, required: true },
  isEpisodeWatched: { type: Function, required: true },
  getEpisodeWatchedAt: { type: Function, required: true },
})

const emit = defineEmits(['watch-option'])

function imgUrl(path) {
  if (!path) return null
  return `https://image.tmdb.org/t/p/w500${path}`
}

function emitWatchOption(episode, option) {
  emit('watch-option', {
    episodeNumber: episode.episode_number,
    option,
    releaseDate: episode.air_date || null,
  })
}
</script>
