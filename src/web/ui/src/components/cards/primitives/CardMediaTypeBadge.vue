<template>
  <span class="badge text-[10px] font-medium" :class="badgeClass">
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import type { MediaType } from '@/types/api'

const props = withDefaults(defineProps<{
  mediaType?: MediaType
}>(), {
  mediaType: MEDIA_TYPE.MOVIE,
})

const isMovie = computed(() => props.mediaType === MEDIA_TYPE.MOVIE)
const label = computed(() => (isMovie.value ? 'MOVIE' : 'SHOW'))
const badgeClass = computed(() => (isMovie.value ? 'bg-blue-500/80 text-blue-100' : 'bg-brand-500/80 text-brand-100'))
</script>
