<template>
  <div class="group block">
    <div class="relative aspect-[2/3] bg-surface-100 rounded-md overflow-hidden">
      <RouterLink :to="linkTo" class="absolute inset-0 z-10" :aria-label="`Open ${title}`" />
      <img
        v-if="posterUrl"
        :src="posterUrl"
        :alt="title"
        class="w-full h-full object-cover transition-[filter] duration-300 group-hover:blur-[2px]"
        loading="lazy"
      />
      <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-500 bg-gradient-to-br from-surface-200 to-surface-100 p-4">
        <svg class="w-10 h-10 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"/>
        </svg>
        <span class="text-xs text-center line-clamp-3">{{ title }}</span>
      </div>

      <!-- Status and rating overlay -->
      <div v-if="statusValue !== 'none' || hasUserRating" class="absolute top-2 right-2 flex items-center gap-1.5">
        <div
          v-if="statusValue !== 'none'"
          class="w-7 h-7 rounded-md flex items-center justify-center shadow-lg"
          :class="statusBadgeClass"
          :title="statusLabel"
          :aria-label="statusLabel"
        >
          <svg v-if="statusValue === WATCH_ENTRY_STATUS.WATCHED" class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
          </svg>
          <svg v-else-if="statusValue === WATCH_ENTRY_STATUS.WATCHING" class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <svg v-else-if="statusValue === WATCH_ENTRY_STATUS.PLAN_TO_WATCH" class="w-4 h-4 text-white" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.4" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
          </svg>
          <svg v-else-if="statusValue === WATCH_ENTRY_STATUS.ON_HOLD" class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M10 7v10M14 7v10"/>
          </svg>
          <svg v-else class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 6l12 12M18 6L6 18"/>
          </svg>
        </div>

        <div
          v-if="hasUserRating"
          class="inline-flex items-center gap-1 rounded-md bg-amber-500/90 px-1.5 py-1 text-[10px] font-semibold text-white shadow-lg"
          :title="`Your rating: ${userRating}/10`"
          :aria-label="`Your rating: ${userRating} out of 10`"
        >
          <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.176 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
          </svg>
          <span>{{ userRating }}</span>
        </div>
      </div>

      <!-- Hover overlay -->
      <div class="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>

      <div
        v-if="showQuickAction || showWatchedQuickAction"
        class="absolute inset-0 z-20 flex items-center justify-center gap-3 opacity-100 transition-opacity duration-200 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
      >
        <button
          v-if="showQuickAction"
          type="button"
          class="w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-indigo-700/90 border-indigo-600 text-white hover:bg-indigo-600"
          :disabled="quickActionLoading"
          :title="quickActionAriaLabel"
          :aria-label="quickActionAriaLabel"
          :aria-pressed="quickActionActive ? 'true' : 'false'"
          :data-pulsing="quickActionPulsing ? 'true' : 'false'"
          @click.stop.prevent="$emit('quick-action-watchlist')"
        >
          <svg v-if="quickActionLoading" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-30" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" />
            <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <svg v-else class="w-4 h-4" :fill="quickActionActive ? 'currentColor' : 'none'" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
          </svg>
        </button>

        <WatchMenu
          v-if="showWatchedQuickAction"
          :release-date="item.release_date || item.first_air_date || ''"
          :button-aria-label="watchedQuickActionAriaLabel"
          :button-title="watchedQuickActionAriaLabel"
          :disabled="watchedQuickActionLoading"
          :pulsing="watchedQuickActionPulsing"
          button-class="w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-emerald-700/90 border-emerald-600 text-white hover:bg-emerald-600"
          menu-class="left-1/2 -translate-x-1/2 bottom-12 mt-0"
          @select="selectWatchOption"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
          </svg>
        </WatchMenu>
      </div>

      <!-- Type badge -->
      <div class="absolute top-2 left-2">
        <span class="badge text-[10px] font-medium" :class="mediaType === MEDIA_TYPE.MOVIE ? 'bg-blue-500/80 text-blue-100' : 'bg-brand-500/80 text-brand-100'">
          {{ mediaType === MEDIA_TYPE.MOVIE ? 'MOVIE' : 'SHOW' }}
        </span>
      </div>
    </div>
    <RouterLink :to="linkTo" class="mt-2 px-0.5 block">
      <p class="text-sm font-medium text-primary truncate group-hover:text-brand-400 transition-colors">{{ title }}</p>
      <div class="mt-0.5 flex items-center gap-2">
        <p class="text-xs text-gray-500">{{ year }}</p>
        <RatingBadge v-if="voteAverage" :value="voteAverage" size="xs" />
      </div>
    </RouterLink>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import RatingBadge from '@/components/RatingBadge.vue'
import WatchMenu from '@/components/WatchMenu.vue'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'

const props = defineProps({
  item: { type: Object, required: true },
  mediaType: { type: String, default: MEDIA_TYPE.MOVIE },
  watched: { type: Boolean, default: false },
  status: { type: String, default: 'none' },
  showQuickAction: { type: Boolean, default: false },
  quickActionActive: { type: Boolean, default: false },
  quickActionLoading: { type: Boolean, default: false },
  quickActionPulsing: { type: Boolean, default: false },
  quickActionAriaLabel: { type: String, default: 'Add to watchlist' },
  showWatchedQuickAction: { type: Boolean, default: false },
  watchedQuickActionLoading: { type: Boolean, default: false },
  watchedQuickActionPulsing: { type: Boolean, default: false },
  watchedQuickActionAriaLabel: { type: String, default: 'Mark as watched' },
})

const emit = defineEmits(['quick-action-watchlist', 'quick-action-watch-option'])

const title = computed(() => props.item.title || props.item.name || '')
const statusValue = computed(() => {
  if (props.status && props.status !== 'none') {
    return props.status
  }
  return props.watched ? WATCH_ENTRY_STATUS.WATCHED : 'none'
})
const statusBadgeClass = computed(() => {
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHED) return 'bg-brand-500'
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHING) return 'bg-blue-600'
  if (statusValue.value === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) return 'bg-indigo-600'
  if (statusValue.value === WATCH_ENTRY_STATUS.ON_HOLD) return 'bg-amber-600'
  if (statusValue.value === WATCH_ENTRY_STATUS.DROPPED) return 'bg-rose-600'
  return 'bg-surface-300'
})
const statusLabel = computed(() => {
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHED) return 'Watched'
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHING) return 'Watching'
  if (statusValue.value === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) return 'Watchlist'
  if (statusValue.value === WATCH_ENTRY_STATUS.ON_HOLD) return 'On hold'
  if (statusValue.value === WATCH_ENTRY_STATUS.DROPPED) return 'Dropped'
  return ''
})
const userRating = computed(() => props.item?.user_status?.rating)
const hasUserRating = computed(() => userRating.value !== null && userRating.value !== undefined)
const posterUrl = computed(() => {
  const path = props.item.poster_path || props.item.poster_url
  if (!path) return null
  if (path.startsWith('http')) return path
  return `https://image.tmdb.org/t/p/w342${path}`
})
const voteAverage = computed(() => props.item.vote_average)
const year = computed(() => {
  const d = props.item.release_date || props.item.first_air_date
  return d ? new Date(d).getFullYear() : ''
})
const linkTo = computed(() => {
  if (props.mediaType === MEDIA_TYPE.TV) return `/tv/${props.item.tmdb_id || props.item.id}`
  return `/movies/${props.item.tmdb_id || props.item.id}`
})

function selectWatchOption(option) {
  emit('quick-action-watch-option', option)
}
</script>
