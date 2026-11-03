<template>
  <button
    type="button"
    class="pointer-events-auto cursor-pointer w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-emerald-700/90 border-emerald-600 text-white hover:bg-emerald-600"
    :disabled="loading"
    :aria-label="label"
    :title="label"
    @click.stop.prevent="handleTrigger"
  >
    <div v-if="loading" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
    <Check v-else class="w-4 h-4" :stroke-width="2.5" />
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check } from '@lucide/vue'
import { useI18n } from '@/i18n'

const props = withDefaults(defineProps<{
  loading?: boolean
  ariaLabel?: string
}>(), {
  loading: false, ariaLabel: '',
})

const { t } = useI18n()
const label = computed(() => props.ariaLabel || t('tracking_mark_as_watched'))

const emit = defineEmits<{
  trigger: []
  'action:upnext-watch': []
}>()

function handleTrigger() {
  emit('action:upnext-watch')
  emit('trigger')
}
</script>
