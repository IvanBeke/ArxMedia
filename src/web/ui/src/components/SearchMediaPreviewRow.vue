<template>
  <div class="flex items-start gap-2">
    <div class="w-[50px] flex-shrink-0 overflow-hidden rounded-sm bg-surface-200">
      <img
        v-if="posterUrl"
        :src="posterUrl"
        :alt="title"
        class="block w-full h-auto"
        loading="lazy"
      />
      <div v-else class="h-[75px] w-full"></div>
    </div>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm text-primary">{{ title }}</p>
      <div class="mt-0.5 flex items-center gap-1 text-[11px] text-muted">
        <span>{{ year || '-' }}</span>
        <span>•</span>
        <span>{{ typeLabel }}</span>
        <span v-if="statusLabel">•</span>
        <span v-if="statusLabel" class="truncate">{{ statusLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { temporalYear } from '@/utils/temporal'

const props = defineProps({
  item: { type: Object, required: true },
})

const title = computed(() => props.item?.title || props.item?.name || 'Untitled')
const year = computed(() => {
  const raw = props.item?.release_date
  return raw ? (temporalYear(raw) || '') : ''
})

const typeLabel = computed(() => props.item?.media_type === MEDIA_TYPE.TV ? 'Show' : 'Movie')

const statusLabel = computed(() => {
  const status = props.item?.user_status?.status
  if (status === WATCH_ENTRY_STATUS.WATCHED) return 'Watched'
  if (status === WATCH_ENTRY_STATUS.WATCHING) return 'Watching'
  if (status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) return 'Watchlist'
  if (status === WATCH_ENTRY_STATUS.DROPPED) return 'Dropped'
  return ''
})

const posterUrl = computed(() => {
  const path = props.item?.poster_path || props.item?.poster_url
  if (!path) return null
  if (path.startsWith('http')) return path
  return `https://image.tmdb.org/t/p/w185${path}`
})
</script>
