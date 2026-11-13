<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/i18n'
import { formatHoursMinutes } from '@/utils/progress'

const props = withDefaults(defineProps<{
  shows?: number | null
  movies?: number | null
  count?: number | null
  typeLabel?: string | null
  totalMinutes?: number
}>(), {
  shows: null, movies: null, count: null, typeLabel: null, totalMinutes: 0,
})

const { t } = useI18n()

const watchedTimeLabel = computed(() => formatHoursMinutes(props.totalMinutes, false, t))

const label = computed(() => {
  const runtimeLabel = watchedTimeLabel.value

  if (props.shows !== null && props.movies !== null) {
    const parts: string[] = []
    if (props.shows > 0) parts.push(t(props.shows === 1 ? 'count_badge_show_one' : 'count_badge_show_many', { count: props.shows }))
    if (props.movies > 0) parts.push(t(props.movies === 1 ? 'count_badge_movie_one' : 'count_badge_movie_many', { count: props.movies }))
    if (parts.length) {
      return `${parts.join(' | ')} | ${runtimeLabel}`
    }
    return runtimeLabel
  }

  if (props.count !== null) {
    if (props.count <= 0) {
      return runtimeLabel
    }
    const labelText = props.typeLabel || t('count_badge_items')
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
