<template>
  <div class="flex items-center gap-2 min-w-0">
    <img
      v-if="avatarUrl"
      :src="avatarUrl"
      :alt="`${user.username} avatar`"
      class="h-6 w-6 rounded-full object-cover border border-surface-200 flex-shrink-0"
      loading="lazy"
    />
    <div v-else class="h-6 w-6 rounded-full bg-brand-500/20 border border-brand-500/30 text-brand-300 text-[10px] font-semibold flex items-center justify-center flex-shrink-0">
      {{ initial }}
    </div>
    <span class="truncate text-sm text-primary">{{ user.username }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  user: { type: Object, required: true },
})

const initial = computed(() => (props.user?.username?.[0] || '?').toUpperCase())
const avatarUrl = computed(() => props.user?.avatar || '')
</script>
