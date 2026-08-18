<template>
  <RatingBadge :value="value" :size="size" :votes="votes" :out-of-ten="outOfTen" />
</template>

<script setup>
import RatingBadge from '@/components/RatingBadge.vue'

defineProps({
  value: { type: [Number, String], required: true },
  votes: { type: [Number, String], default: 0 },
  size: { type: String, default: 'xs' },
  outOfTen: { type: Boolean, default: false },
})
</script>
