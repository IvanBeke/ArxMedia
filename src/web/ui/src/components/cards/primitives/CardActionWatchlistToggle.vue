<template>
  <button
    type="button"
    class="pointer-events-auto cursor-pointer w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-indigo-700/90 border-indigo-600 text-white hover:bg-indigo-600"
    :disabled="loading"
    :title="ariaLabel"
    :aria-label="ariaLabel"
    :aria-pressed="active ? 'true' : 'false'"
    :data-pulsing="pulsing ? 'true' : 'false'"
    @click.stop.prevent="handleTrigger"
  >
    <svg v-if="loading" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle class="opacity-30" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" />
      <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    </svg>
    <svg v-else class="w-4 h-4" :fill="active ? 'currentColor' : 'none'" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
    </svg>
  </button>
</template>

<script setup>
defineProps({
  active: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  pulsing: { type: Boolean, default: false },
  ariaLabel: { type: String, default: 'Add to watchlist' },
})

const emit = defineEmits(['trigger', 'action:watchlist-toggle'])

function handleTrigger() {
  emit('action:watchlist-toggle')
  emit('trigger')
}
</script>
