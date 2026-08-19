<template>
  <button
    type="button"
    class="pointer-events-auto cursor-pointer w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-rose-700/90 border-rose-600 text-white hover:bg-rose-600"
    :disabled="loading"
    :aria-label="ariaLabel"
    :title="ariaLabel"
    @click.stop.prevent="handleTrigger"
  >
    <div v-if="loading" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
    <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
    </svg>
  </button>
</template>

<script setup>
const props = defineProps({
  loading: { type: Boolean, default: false },
  ariaLabel: { type: String, default: 'Remove history entry' },
  confirmText: { type: String, default: '' },
})

const emit = defineEmits(['trigger', 'action:history-remove'])

function handleTrigger() {
  if (props.confirmText && !window.confirm(props.confirmText)) {
    return
  }
  emit('action:history-remove')
  emit('trigger')
}
</script>
