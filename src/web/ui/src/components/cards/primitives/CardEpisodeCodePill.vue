<template>
  <EpisodeCodePill
    :season-number="seasonNumber"
    :episode-number="episodeNumber"
    :variant="variant"
    :size="size"
    :class="extraClass"
  />
</template>

<script setup lang="ts">
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'

withDefaults(defineProps<{
  seasonNumber?: number | string | null
  episodeNumber?: number | string | null
  variant?: string
  size?: string
  extraClass?: string
}>(), {
  seasonNumber: null, episodeNumber: null, variant: 'pill', size: 'sm', extraClass: '',
})
</script>
