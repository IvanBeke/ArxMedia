<template>
  <div>
    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      <div v-for="n in 10" :key="n" class="aspect-[2/3] skeleton rounded-md"></div>
    </div>
    <p v-else-if="loadError" class="text-sm text-muted">Recommendations unavailable right now.</p>
    <div v-else-if="items.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      <MediaCard
        v-for="item in items"
        :key="`${item.media_type}-${item.id}`"
        :item="item"
        :media-type="item.media_type || mediaType"
        @error="showQuickActionError"
        @status-changed="emit('status-changed', $event)"
        @watchlist-removed="emit('watchlist-removed', $event)"
      />
    </div>
    <p v-else class="text-sm text-muted">No recommendations found.</p>
  </div>
</template>

<script setup lang="ts">
import MediaCard from '@/components/MediaCard.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useFlashMessages } from '@/composables/useFlashMessages'
import type { MediaResult, MediaType } from '@/types/api'
import type { MediaStatusChangedPayload } from '@/utils/mediaStatusSync'

withDefaults(defineProps<{
  items: MediaResult[]
  mediaType?: MediaType
  loading?: boolean
  loadError?: boolean
}>(), { mediaType: MEDIA_TYPE.MOVIE, loading: false, loadError: false })

const emit = defineEmits<{
  'status-changed': [payload: MediaStatusChangedPayload]
  'watchlist-removed': [payload: { tmdb_id: number | undefined; media_type: MediaType }]
}>()

const { errorMsg: quickActionError, showError: showQuickActionError } = useFlashMessages()
</script>
