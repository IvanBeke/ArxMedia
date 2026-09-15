<template>
  <div class="flex items-center gap-2 min-w-0">
    <img
      v-if="profileUrl"
      :src="profileUrl"
      :alt="`${person.name} profile photo`"
      class="h-6 w-6 rounded-full object-cover border border-surface-200 flex-shrink-0"
      loading="lazy"
    />
    <div v-else class="h-6 w-6 rounded-full bg-brand-500/20 border border-brand-500/30 text-brand-300 text-[10px] font-semibold flex items-center justify-center flex-shrink-0">
      {{ initial }}
    </div>
    <span class="truncate text-sm text-primary">{{ person.name }}</span>
    <span v-if="person.known_for_department" class="truncate text-xs text-muted">{{ person.known_for_department }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { tmdbImageUrl } from '@/utils/images'
import type { PersonSearchResult } from '@/types/api'

const props = defineProps<{
  person: PersonSearchResult
}>()

const initial = computed(() => (props.person.name.trim()[0] || '?').toUpperCase())
const profileUrl = computed(() => tmdbImageUrl(props.person.profile_path, 'w185') || '')
</script>
