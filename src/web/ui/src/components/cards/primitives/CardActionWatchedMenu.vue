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
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
      </svg>
    </WatchMenu>
  </div>
</template>

<script setup>
import WatchMenu from '@/components/WatchMenu.vue'

defineProps({
  releaseDate: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  pulsing: { type: Boolean, default: false },
  ariaLabel: { type: String, default: 'Mark as watched' },
})

const emit = defineEmits(['select', 'action:watched-select'])

function handleSelect(option) {
  emit('action:watched-select', option)
  emit('select', option)
}
</script>
