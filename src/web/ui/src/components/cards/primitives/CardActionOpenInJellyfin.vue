<template>
  <a
    :href="url"
    target="_blank"
    rel="noopener noreferrer"
    class="pointer-events-auto cursor-pointer w-10 h-10 rounded-full flex items-center justify-center border shadow-lg transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-400 focus-visible:ring-offset-surface bg-brand-500/95 border-brand-400 text-white hover:bg-brand-600"
    :aria-label="label"
    :title="label"
    @click.stop
  >
    <Play class="w-4 h-4" fill="currentColor" aria-hidden="true" />
  </a>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Play } from '@lucide/vue'
import { useI18n } from '@/i18n'

defineProps<{ url: string }>()

const { t } = useI18n()
const label = computed(() => t('jellyfin_open'))
</script>
