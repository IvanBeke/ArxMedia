<template>
  <WatchMenu
    :release-date="releaseDate"
    :button-title="tooltipText"
    :disabled="disabled"
    :pulsing="pulsing"
    @select="(option) => $emit('select', option)"
  >
    <span
      class="flex items-center justify-center w-8 h-8 rounded-md transition-colors duration-200"
      :class="watched ? 'bg-brand-500 text-white hover:bg-brand-600' : 'bg-surface-200 text-gray-500 hover:text-white hover:bg-surface-300'"
    >
      <svg v-if="watched" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
      </svg>
      <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
      </svg>
    </span>
  </WatchMenu>
</template>

<script setup>
import { computed } from 'vue'
import WatchMenu from '@/components/WatchMenu.vue'
import { formatDateTimeByLocale, useI18n } from '@/i18n'

const props = defineProps({
  watched: { type: Boolean, default: false },
  watchedAt: { type: String, default: '' },
  releaseDate: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  pulsing: { type: Boolean, default: false },
})

defineEmits(['select'])

const { t } = useI18n()

const tooltipText = computed(() => {
  if (!props.watched) return t('tracking_mark_as_watched')
  if (!props.watchedAt) return t('tracking_watched')
  const formatted = formatDateTimeByLocale(props.watchedAt)
  if (!formatted) return t('tracking_watched')
  return `${t('tracking_watched_on')} ${formatted}`
})
</script>
