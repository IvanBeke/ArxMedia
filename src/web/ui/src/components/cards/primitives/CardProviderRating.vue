<template>
  <RatingBadge :value="value" :size="size" :votes="votes" :out-of-ten="outOfTen" />
</template>

<script setup lang="ts">
import RatingBadge from '@/components/RatingBadge.vue'

withDefaults(defineProps<{
  value: number | string
  votes?: number | string
  size?: string
  outOfTen?: boolean
}>(), {
  votes: 0, size: 'xs', outOfTen: false,
})
</script>
