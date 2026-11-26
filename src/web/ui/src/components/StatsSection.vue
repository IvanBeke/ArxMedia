<template>
  <section class="card p-4 md:p-5">
    <h2 class="section-title mb-4">{{ title }}</h2>
    <StatsState :loading="loading" :error="error" @retry="emit('retry')">
      <slot />
    </StatsState>
  </section>
</template>

<script setup lang="ts">
import StatsState from '@/components/StatsState.vue'

defineProps<{
  title: string
  loading?: boolean
  error?: boolean
}>()
const emit = defineEmits<{ retry: [] }>()
</script>
