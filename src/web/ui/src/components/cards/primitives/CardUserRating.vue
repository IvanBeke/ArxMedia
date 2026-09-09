<template>
  <UserRating :value="value" :size="size" />
</template>

<script setup lang="ts">
import UserRating from '@/components/UserRating.vue'

withDefaults(defineProps<{
  value: number | string
  size?: string
}>(), {
  size: 'xs',
})
</script>
