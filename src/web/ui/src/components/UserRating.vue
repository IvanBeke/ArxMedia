<template>
  <span
    class="inline-flex items-center rounded-md bg-amber-500/90 text-white shadow-lg"
    :class="sizeClass"
    :title="label"
    :aria-label="ariaLabel"
  >
    <svg :class="iconClass" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.176 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
    </svg>
    <span class="font-semibold leading-none">{{ displayValue }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: [Number, String], required: true },
  size: { type: String, default: 'sm' },
  titlePrefix: { type: String, default: 'Your rating' },
})

const numericValue = computed(() => Number(props.value))

const displayValue = computed(() => {
  if (!Number.isFinite(numericValue.value)) return String(props.value)
  if (Number.isInteger(numericValue.value)) return String(numericValue.value)
  return numericValue.value.toFixed(1)
})

const label = computed(() => `${props.titlePrefix}: ${displayValue.value}/10`)
const ariaLabel = computed(() => `${props.titlePrefix}: ${displayValue.value} out of 10`)

const sizeClass = computed(() => {
  if (props.size === 'xs') return 'gap-1 px-1.5 py-1 text-[10px]'
  return 'gap-1 px-2 py-1 text-xs'
})

const iconClass = computed(() => {
  if (props.size === 'xs') return 'w-3 h-3'
  return 'w-3.5 h-3.5'
})
</script>
