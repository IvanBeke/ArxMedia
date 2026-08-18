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
        <UserRating v-if="hasRating" :value="rating" size="xs" class="absolute top-2 right-2" />
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
      <slot name="meta" :subtitle="subtitle" :subtitle-show-title="subtitleShowTitle" :timestamp-label="timestampLabel" :entry="entry">
        <p v-if="showMeta && (subtitle || hasEpisodeCode)" class="text-xs text-muted">
          <span v-if="subtitleShowTitle">{{ subtitleShowTitle }} · </span>
          <EpisodeCodePill
            v-if="hasEpisodeCode"
            :season-number="entry.season_number"
            :episode-number="entry.episode_number"
            variant="plain"
          />
          <span v-else>{{ subtitle }}</span>
        </p>
        <p v-if="showTimestamp && timestampLabel" class="text-xs text-muted">{{ timestampLabel }}</p>
      </slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'
import UserRating from '@/components/UserRating.vue'
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

const hasEpisodeCode = computed(() => {
  return Boolean(isEpisode.value && props.entry.season_number && props.entry.episode_number)
})

const subtitle = computed(() => {
  if (!isEpisode.value) {
    return ''
  }
  const seasonNumber = props.entry.season_number
  const episodeNumber = props.entry.episode_number
  if (!seasonNumber || !episodeNumber) {
    return props.entry.show_title || props.entry.show_name || ''
  }
  const showTitle = props.entry.show_title || props.entry.show_name || ''
  if (!showTitle || showTitle === displayTitle.value) {
    return ''
  }
  return showTitle
})

const subtitleShowTitle = computed(() => {
  if (!isEpisode.value) return ''
  const showTitle = props.entry.show_title || props.entry.show_name || ''
  if (!showTitle || showTitle === displayTitle.value) return ''
  return showTitle
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
