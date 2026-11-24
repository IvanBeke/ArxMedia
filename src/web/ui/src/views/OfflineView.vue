<template>
  <div class="max-w-xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
    <WifiOff class="mx-auto h-12 w-12 text-muted" aria-hidden="true" />
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
import { usePageTitle } from '@/composables/usePageTitle'
import { WifiOff } from '@lucide/vue'

const router = useRouter()
const { t } = useI18n()
usePageTitle(() => t('pwa_offline_title'))

function retry(): void {
  if (navigator.onLine) {
    void router.push('/')
  } else {
    window.location.reload()
  }
}
</script>
