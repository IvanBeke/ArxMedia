<template>
  <IntegrationButton
    v-if="stateKnown"
    :service="INTEGRATION_SERVICE.SONARR"
    :label="state.added ? t('sonarr_in_button') : t('sonarr_add_button')"
    :active="state.added"
    @click="dialog?.showModal()"
  />
  <AddToSonarrDialog
    ref="dialog"
    :tmdb-id="tmdbId"
    :title="title"
    @synced="state = $event"
    @added="emit('added')"
    @removed="emit('removed')"
  />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { integrationsAPI } from '@/api'
import AddToSonarrDialog from '@/components/AddToSonarrDialog.vue'
import IntegrationButton from '@/components/IntegrationButton.vue'
import { INTEGRATION_SERVICE } from '@/constants/integrations'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'
import { useI18n } from '@/i18n'
import type { ArrItemState } from '@/types/api'

const props = defineProps<{ tmdbId: string | number; title: string }>()
const emit = defineEmits<{ added: []; removed: [] }>()

const { t } = useI18n()
const { next: nextRequest } = useLatestRequest()
const dialog = ref<InstanceType<typeof AddToSonarrDialog> | null>(null)
const state = ref<ArrItemState>({ added: false })
const stateKnown = ref(false)

async function loadState() {
  const signal = nextRequest()
  stateKnown.value = false
  state.value = { added: false }
  try {
    state.value = await integrationsAPI.getSonarrSeries(props.tmdbId, { signal })
  } catch (error) {
    if (isAbortError(error)) return
  }
  stateKnown.value = true
}

watch(() => props.tmdbId, loadState, { immediate: true })
</script>
