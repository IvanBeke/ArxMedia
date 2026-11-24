<template>
  <span
    class="inline-flex items-center rounded-md bg-amber-500/90 user-rating-text shadow-lg"
    :class="sizeClass"
    :title="label"
    :aria-label="ariaLabel"
  >
    <Star :class="iconClass" fill="currentColor" :stroke-width="0" aria-hidden="true" />
    <span class="font-semibold leading-none">{{ displayValue }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/i18n'
import { formatRating } from '@/utils/format'
import { Star } from '@lucide/vue'

const props = withDefaults(defineProps<{
  value: number | string
  size?: string
  titlePrefix?: string
}>(), {
  size: 'sm',
})

const { t } = useI18n()

const numericValue = computed(() => Number(props.value))

const displayValue = computed(() => {
  if (!Number.isFinite(numericValue.value)) return String(props.value)
  if (Number.isInteger(numericValue.value)) return String(numericValue.value)
  return formatRating(numericValue.value)
})

const prefix = computed(() => props.titlePrefix ?? t('user_rating_prefix'))
const label = computed(() => t('user_rating_title', { prefix: prefix.value, value: displayValue.value }))
const ariaLabel = computed(() => t('user_rating_aria', { prefix: prefix.value, value: displayValue.value }))

const sizeClass = computed(() => {
  if (props.size === 'xs') return 'gap-1 px-1.5 py-1 text-[10px]'
  return 'gap-1 px-2 py-1 text-xs'
})

const iconClass = computed(() => {
  if (props.size === 'xs') return 'w-3 h-3'
  return 'w-3.5 h-3.5'
})
</script>

<style scoped>
.user-rating-text {
  color: var(--user-rating-text);
}
</style>
