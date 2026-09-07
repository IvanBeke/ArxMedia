<script setup>
import { computed } from 'vue'
import { formatHoursMinutes } from '@/utils/progress'

const props = defineProps({
  shows: { type: Number, default: null },
  movies: { type: Number, default: null },
  count: { type: Number, default: null },
  typeLabel: { type: String, default: null },
  totalMinutes: { type: Number, default: 0 },
})

const watchedTimeLabel = computed(() => formatHoursMinutes(props.totalMinutes))

const label = computed(() => {
  const runtimeLabel = watchedTimeLabel.value

  if (props.shows !== null && props.movies !== null) {
    const parts = []
    if (props.shows > 0) parts.push(`${props.shows} show${props.shows === 1 ? '' : 's'}`)
    if (props.movies > 0) parts.push(`${props.movies} movie${props.movies === 1 ? '' : 's'}`)
    if (parts.length) {
      return `${parts.join(' | ')} | ${runtimeLabel}`
    }
    return runtimeLabel
  }

  if (props.count !== null) {
    if (props.count <= 0) {
      return runtimeLabel
    }
    const labelText = props.typeLabel || 'items'
    return `${props.count} ${labelText} | ${runtimeLabel}`
  }

  return runtimeLabel
})
</script>

<template>
  <div
    class="inline-flex items-center gap-2 rounded-full border border-surface-200 bg-surface-100 px-3 py-1 text-xs text-secondary"
    data-testid="count-runtime-badge"
  >
    <span class="h-1.5 w-1.5 rounded-full bg-brand-500" aria-hidden="true"></span>
    <span>{{ label }}</span>
  </div>
</template>
