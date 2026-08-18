<template>
  <EpisodeCodePill
    :season-number="seasonNumber"
    :episode-number="episodeNumber"
    :variant="variant"
    :size="size"
    :class="extraClass"
  />
</template>

<script setup>
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'

defineProps({
  seasonNumber: { type: [Number, String], default: null },
  episodeNumber: { type: [Number, String], default: null },
  variant: { type: String, default: 'pill' },
  size: { type: String, default: 'sm' },
  extraClass: { type: String, default: '' },
})
</script>
