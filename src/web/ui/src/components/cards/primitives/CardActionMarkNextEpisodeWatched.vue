<template>
  <button
    type="button"
    class="pointer-events-auto cursor-pointer w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-brand-500/95 border-brand-400 text-white hover:bg-brand-600"
    :disabled="loading"
    :aria-label="ariaLabel"
    :title="ariaLabel"
    @click.stop.prevent="handleTrigger"
  >
    <div v-if="loading" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
    <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5v14l11-7z"/>
    </svg>
  </button>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  ariaLabel: { type: String, default: 'Mark next episode watched' },
})

const emit = defineEmits(['trigger', 'action:upnext-watch'])

function handleTrigger() {
  emit('action:upnext-watch')
  emit('trigger')
}
</script>
