<template>
  <ul class="text-sm">
    <li v-for="slice in slices" :key="slice.key" class="flex items-center gap-2" :class="slice.colorClass">
      <span class="w-3 h-3 rounded-full shrink-0 bg-current"></span>
      <span class="text-secondary truncate">{{ slice.label }}</span>
      <span class="text-primary font-medium before:content-['·'] before:mr-2 before:font-normal before:text-muted">{{ slice.display ?? slice.value }}</span>
      <span class="text-muted text-xs before:content-['·'] before:mr-2">{{ slice.percent }}%</span>
    </li>
  </ul>
</template>

<script setup lang="ts">
import type { StatSlice } from '@/types/stats'

defineProps<{ slices: StatSlice[] }>()
</script>
