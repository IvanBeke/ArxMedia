<template>
  <div class="card p-4">
    <p class="text-2xl font-display text-brand-500">{{ value }}</p>
    <p class="text-muted text-xs mt-1">{{ title }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
}>()
</script>
