<template>
  <div v-if="loading" class="space-y-3">
    <div class="h-6 w-48 skeleton rounded-md"></div>
    <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">
      <div v-for="n in 6" :key="n" class="aspect-[2/3] skeleton rounded-md"></div>
    </div>
  </div>
  <div v-else-if="collection">
    <div class="flex items-start gap-4 mb-4">
      <img
        v-if="collection.poster_path"
        :src="tmdbImageUrl(collection.poster_path, 'w185') || ''"
        :alt="collection.name"
        class="w-16 rounded-md border border-surface-200"
        loading="lazy"
        decoding="async"
      />
      <div class="min-w-0">
        <p class="text-xs text-gray-500 uppercase tracking-wider mb-1">Part of</p>
        <h3 class="text-primary font-medium">{{ collection.name }}</h3>
        <p v-if="overview" class="text-sm text-muted mt-1 line-clamp-3 max-w-2xl">{{ overview }}</p>
      </div>
    </div>
    <RecommendationsRow :items="parts" :media-type="MEDIA_TYPE.MOVIE" @status-changed="handleStatusChanged" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import RecommendationsRow from '@/components/RecommendationsRow.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { tmdbImageUrl } from '@/utils/images'
import { applyStatusChanged, sortMediaByReleaseDate, type MediaStatusChangedPayload } from '@/utils/mediaStatusSync'
import type { CollectionDetail, MediaResult } from '@/types/api'

const props = withDefaults(defineProps<{
  collection?: CollectionDetail | null
  loading?: boolean
}>(), { collection: null, loading: false })

const overview = computed(() => props.collection?.overview || '')

const parts = computed((): MediaResult[] => {
  const rawParts = props.collection?.parts
  if (!Array.isArray(rawParts)) return []
  return sortMediaByReleaseDate(
    rawParts.map((part) => ({
      ...part,
      media_type: 'movie' as const,
    })),
  )
})

function handleStatusChanged(payload: MediaStatusChangedPayload) {
  const source = props.collection?.parts
  if (Array.isArray(source)) {
    applyStatusChanged(source, payload)
  }
}
</script>
