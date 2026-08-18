<template>
  <div
    class="w-7 h-7 rounded-md flex items-center justify-center shadow-lg"
    :class="statusBadgeClass"
    :title="statusTooltip"
    :aria-label="statusTooltip"
    tabindex="0"
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
    <svg v-else class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 6l12 12M18 6L6 18"/>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { WATCH_ENTRY_STATUS } from '@/constants/tracking'

const props = defineProps({
  status: { type: String, default: 'none' },
  watched: { type: Boolean, default: false },
})

const statusValue = computed(() => {
  if (props.status && props.status !== 'none') {
    return props.status
  }
  return props.watched ? WATCH_ENTRY_STATUS.WATCHED : 'none'
})

const statusBadgeClass = computed(() => {
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHED) return 'bg-emerald-600'
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHING) return 'bg-brand-500'
  if (statusValue.value === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) return 'bg-indigo-600'
  if (statusValue.value === WATCH_ENTRY_STATUS.DROPPED) return 'bg-rose-600'
  return 'bg-surface-300'
})

const statusLabel = computed(() => {
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHED) return 'Watched'
  if (statusValue.value === WATCH_ENTRY_STATUS.WATCHING) return 'Watching'
  if (statusValue.value === WATCH_ENTRY_STATUS.PLAN_TO_WATCH) return 'Watchlist'
  if (statusValue.value === WATCH_ENTRY_STATUS.DROPPED) return 'Dropped'
  return ''
})

const statusTooltip = computed(() => {
  if (!statusLabel.value) return ''
  return `Status: ${statusLabel.value}`
})
</script>
