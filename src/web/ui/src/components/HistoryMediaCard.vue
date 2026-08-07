<template>
  <div class="group">
    <RouterLink :to="resolvedPosterLinkTo" class="block">
      <div class="relative w-full aspect-[2/3] rounded-lg overflow-hidden bg-surface-200">
        <img
          v-if="posterUrl"
          :src="posterUrl"
          :alt="displayTitle"
          class="w-full h-full object-cover group-hover:opacity-80 transition-opacity"
          loading="lazy"
        />
        <div v-else class="w-full h-full flex items-center justify-center">
          <svg class="w-12 h-12 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 16h4m10 0h4M4 4h16v16H4z"/>
          </svg>
        </div>
        <div
          v-if="hasRating"
          class="absolute top-2 right-2 inline-flex items-center gap-1 rounded-md bg-amber-500/90 px-1.5 py-1 text-[10px] font-semibold text-white shadow-lg"
          :title="`Your rating: ${rating}/10`"
          :aria-label="`Your rating: ${rating} out of 10`"
        >
          <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.176 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
          </svg>
          <span>{{ rating }}</span>
        </div>
        <div v-if="$slots['poster-badge']" class="absolute top-2 left-2 z-10">
          <slot name="poster-badge" />
        </div>
      </div>
    </RouterLink>
    <slot name="title" :display-title="displayTitle" :title-link-to="resolvedTitleLinkTo" :entry="entry">
      <RouterLink :to="resolvedTitleLinkTo" class="block p-2">
        <p class="text-sm text-primary font-medium truncate hover:text-brand-400">{{ displayTitle }}</p>
      </RouterLink>
    </slot>
    <div class="px-2 pb-2 space-y-1">
      <slot name="meta" :subtitle="subtitle" :timestamp-label="timestampLabel" :entry="entry">
        <p v-if="showMeta && subtitle" class="text-xs text-muted">{{ subtitle }}</p>
        <p v-if="showTimestamp && timestampLabel" class="text-xs text-muted">{{ timestampLabel }}</p>
      </slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'

const props = defineProps({
  entry: { type: Object, required: true },
  linkTo: { type: String, required: true },
  posterLinkTo: { type: String, default: '' },
  titleLinkTo: { type: String, default: '' },
  timestamp: { type: String, default: '' },
  timestampText: { type: String, default: '' },
  showMeta: { type: Boolean, default: true },
  showTimestamp: { type: Boolean, default: true },
})

const resolvedPosterLinkTo = computed(() => props.posterLinkTo || props.linkTo)
const resolvedTitleLinkTo = computed(() => props.titleLinkTo || props.linkTo)

const isEpisode = computed(() => props.entry.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE)

const displayTitle = computed(() => {
  if (isEpisode.value && props.entry.episode_title) {
    return props.entry.episode_title
  }
  if (props.entry.title) {
    return props.entry.title
  }
  return isEpisode.value ? 'Episode' : 'Unknown'
})

const posterUrl = computed(() => {
  const path = props.entry.poster_url || props.entry.poster_path
  if (!path) return null
  if (path.startsWith('http')) return path
  return `https://image.tmdb.org/t/p/w342${path}`
})

const rating = computed(() => {
  if (props.entry.rating !== null && props.entry.rating !== undefined) {
    return props.entry.rating
  }
  return props.entry.user_status?.rating
})

const hasRating = computed(() => rating.value !== null && rating.value !== undefined)

const subtitle = computed(() => {
  if (!isEpisode.value) {
    return ''
  }
  const seasonNumber = props.entry.season_number
  const episodeNumber = props.entry.episode_number
  if (!seasonNumber || !episodeNumber) {
    return props.entry.show_title || props.entry.show_name || ''
  }
  const code = `S${String(seasonNumber).padStart(2, '0')}E${String(episodeNumber).padStart(2, '0')}`
  const showTitle = props.entry.show_title || props.entry.show_name || ''
  if (!showTitle || showTitle === displayTitle.value) {
    return code
  }
  return `${showTitle} · ${code}`
})

const timestampLabel = computed(() => {
  if (props.timestampText) {
    return props.timestampText
  }
  const rawTimestamp = props.timestamp || props.entry.watched_at
  if (!rawTimestamp) return ''
  const date = new Date(rawTimestamp)
  if (Number.isNaN(date.getTime())) return ''
  const datePart = date.toLocaleDateString('en-GB')
  const timePart = date.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${datePart} · ${timePart}`
})
</script>
