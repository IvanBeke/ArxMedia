<template>
  <div role="alert" class="card p-6 text-center">
    <p class="text-secondary">{{ message }}</p>
    <button type="button" class="btn-primary text-sm mt-4" @click="emit('retry')">Try again</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
const emit = defineEmits<{ retry: [] }>()
</script>
