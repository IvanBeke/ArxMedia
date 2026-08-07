<template>
  <span class="inline-flex items-center gap-2">
    <span class="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 text-amber-700" :class="sizeClass">
      <svg :class="iconClass" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
      </svg>
      <span :class="valueClass">{{ displayValue }}</span>
      <span v-if="outOfTen" :class="suffixClass">/10</span>
    </span>
    <span v-if="showVotes" class="text-gray-500 text-xs">({{ formattedVotes }} {{ voteLabel }})</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '@/i18n'

const props = defineProps({
  value: { type: [Number, String], required: true },
  decimals: { type: Number, default: 1 },
  outOfTen: { type: Boolean, default: false },
  size: { type: String, default: 'sm' },
  votes: { type: [Number, String], default: 0 }
})

const { t } = useI18n()

const votesNumber = computed(() => Number(props.votes))

const showVotes = computed(() => Number.isFinite(votesNumber.value) && votesNumber.value > 0)

const formattedVotes = computed(() => {
  if (!showVotes.value) return '0'
  return votesNumber.value.toLocaleString()
})

const voteLabel = computed(() => {
  if (votesNumber.value === 1) return t('rating_vote_singular')
  return t('rating_vote_plural')
})

const displayValue = computed(() => {
  if (typeof props.value === 'number' && Number.isFinite(props.value)) {
    return props.value.toFixed(props.decimals)
  }
  return String(props.value)
})

const sizeClass = computed(() => {
  if (props.size === 'xs') return 'gap-1 px-2 py-0.5 text-[11px]'
  if (props.size === 'lg') return 'gap-1.5 px-3 py-1 text-base'
  return 'gap-1 px-2.5 py-1 text-sm'
})

const iconClass = computed(() => {
  if (props.size === 'xs') return 'w-3 h-3'
  if (props.size === 'lg') return 'w-5 h-5'
  return 'w-4 h-4'
})

const valueClass = computed(() => {
  if (props.size === 'xs') return 'font-semibold'
  return 'font-semibold'
})

const suffixClass = computed(() => {
  if (props.size === 'xs') return 'text-[10px]'
  return 'text-xs'
})
</script>
