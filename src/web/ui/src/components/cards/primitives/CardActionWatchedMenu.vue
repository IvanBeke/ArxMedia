<template>
  <div class="pointer-events-auto">
    <WatchMenu
      :release-date="releaseDate"
      :button-aria-label="ariaLabel"
      :button-title="ariaLabel"
      :disabled="loading"
      :pulsing="pulsing"
      button-class="w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-emerald-700/90 border-emerald-600 text-white hover:bg-emerald-600"
      menu-class="left-1/2 -translate-x-1/2 bottom-12 mt-0"
      @select="handleSelect"
    >
      <Check class="w-4 h-4" :stroke-width="2.5" />
    </WatchMenu>
  </div>
</template>

<script setup lang="ts">
import { Check } from '@lucide/vue'
import WatchMenu from '@/components/WatchMenu.vue'
import type { WatchedAtOption } from '@/utils/watchOptions'

withDefaults(defineProps<{
  releaseDate?: string
  loading?: boolean
  pulsing?: boolean
  ariaLabel?: string
}>(), {
  releaseDate: '', loading: false, pulsing: false, ariaLabel: 'Mark as watched',
})

const emit = defineEmits<{
  select: [option: WatchedAtOption]
  'action:watched-select': [option: WatchedAtOption]
}>()

function handleSelect(option: WatchedAtOption) {
  emit('action:watched-select', option)
  emit('select', option)
}
</script>
