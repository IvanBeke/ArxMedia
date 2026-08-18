<template>
  <UserRating :value="value" :size="size" />
</template>

<script setup>
import UserRating from '@/components/UserRating.vue'

defineProps({
  value: { type: [Number, String], required: true },
  size: { type: String, default: 'xs' },
})
</script>
