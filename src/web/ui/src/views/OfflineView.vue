<template>
  <div class="max-w-xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
    <svg
      class="mx-auto h-12 w-12 text-muted"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M5 12.55a11 11 0 0 1 14.08 0M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01M1.42 9a16 16 0 0 1 21.16 0"
      />
      <path stroke-linecap="round" stroke-width="2" d="M3 3l18 18" />
    </svg>
    <h1 class="mt-4 font-display text-2xl font-semibold text-primary">{{ t('pwa_offline_title') }}</h1>
    <p class="mt-2 text-sm text-secondary">{{ t('pwa_offline_desc') }}</p>
    <button type="button" class="btn-primary mt-6 px-4 py-2 text-sm" @click="retry">
      {{ t('pwa_offline_retry') }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from '@/i18n'

const router = useRouter()
const { t } = useI18n()

function retry(): void {
  if (navigator.onLine) {
    void router.push('/')
  } else {
    window.location.reload()
  }
}
</script>
