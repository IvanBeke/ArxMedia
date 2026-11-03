<template>
  <IntegrationButton v-if="url" :service="INTEGRATION_SERVICE.JELLYFIN" :label="t('jellyfin_open')" :href="url" />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { integrationsAPI } from '@/api'
import IntegrationButton from '@/components/IntegrationButton.vue'
import { INTEGRATION_SERVICE } from '@/constants/integrations'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'
import { useI18n } from '@/i18n'

const props = defineProps<{
  tmdbId: number
  scope: 'movie' | 'show' | 'season' | 'episode'
  seasonNumber?: number
  episodeNumber?: number
}>()

const { t } = useI18n()
const { next: nextRequest } = useLatestRequest()
const url = ref('')

async function fetchUrl(signal: AbortSignal): Promise<string | null> {
  if (props.scope === 'movie') {
    return (await integrationsAPI.getJellyfinMovieLink(props.tmdbId, { signal })).url
  }
  const params = props.scope === 'show' ? {} : { season: props.seasonNumber, episode: props.scope === 'episode' ? props.episodeNumber : undefined }
  const links = await integrationsAPI.getJellyfinLinks(props.tmdbId, params, { signal })
  return links[`${props.scope}_url`]
}

async function loadUrl() {
  const signal = nextRequest()
  url.value = ''
  try {
    url.value = (await fetchUrl(signal)) ?? ''
  } catch (error) {
    if (isAbortError(error)) return
  }
}

watch(() => [props.tmdbId, props.scope, props.seasonNumber, props.episodeNumber], loadUrl, { immediate: true })
</script>
