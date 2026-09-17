<template>
  <div
    class="pointer-events-none fixed inset-x-4 bottom-4 z-[110] flex flex-col items-center gap-2"
    aria-live="polite"
  >
    <div
      v-if="showOffline"
      role="alert"
      class="pointer-events-auto w-full max-w-md rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-2.5 text-center text-sm text-yellow-200"
    >
      {{ t('pwa_offline_banner') }}
      <RouterLink to="/offline" class="ml-1 font-medium underline underline-offset-2">
        {{ t('pwa_offline_title') }}
      </RouterLink>
    </div>

    <div
      v-if="showUpdate"
      role="alertdialog"
      aria-label="Update available"
      class="pointer-events-auto w-full max-w-md rounded-lg border border-surface-200 bg-surface px-4 py-3 shadow-xl"
    >
      <p class="text-sm font-medium text-primary">{{ t('pwa_update_title') }}</p>
      <p class="mt-0.5 text-xs text-muted">{{ t('pwa_update_desc') }}</p>
      <div class="mt-2 flex justify-end gap-2">
        <button type="button" class="btn-ghost text-sm px-3 py-1.5" @click="updateDismissed = true">
          {{ t('pwa_update_dismiss') }}
        </button>
        <button type="button" class="btn-primary text-sm px-3 py-1.5" @click="update">
          {{ t('pwa_update_action') }}
        </button>
      </div>
    </div>

    <div
      v-if="showInstall"
      role="dialog"
      aria-label="Install app"
      class="pointer-events-auto w-full max-w-md rounded-lg border border-surface-200 bg-surface px-4 py-3 shadow-xl"
    >
      <p class="text-sm font-medium text-primary">{{ t('pwa_install_title') }}</p>
      <p class="mt-0.5 text-xs text-muted">{{ t('pwa_install_desc') }}</p>
      <div class="mt-2 flex justify-end gap-2">
        <button type="button" class="btn-ghost text-sm px-3 py-1.5" @click="dismissInstall">
          {{ t('pwa_install_dismiss') }}
        </button>
        <button type="button" class="btn-primary text-sm px-3 py-1.5" @click="install">
          {{ t('pwa_install_action') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from '@/i18n'
import { usePwa } from '@/composables/usePwa'

const { t } = useI18n()
const { needRefresh, isOnline, canInstall, install, dismissInstall, update } = usePwa()

const updateDismissed = ref(false)
const showUpdate = computed(() => needRefresh.value && !updateDismissed.value)
// Read `.value` explicitly so these stay plain booleans even when the
// service-worker state is stubbed (tests, unsupported browsers).
const showOffline = computed(() => !isOnline.value)
const showInstall = computed(() => canInstall.value)

watch(
  () => needRefresh.value,
  (refresh) => {
    if (refresh) updateDismissed.value = false
  },
)
</script>
