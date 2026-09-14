<template>
  <div v-if="people.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 text-sm">
    <div v-for="person in people" :key="person.credit_id || `${person.id}-${person.character}`" class="flex items-center gap-3 min-w-0">
      <img
        v-if="person.profile_path"
        :src="tmdbImageUrl(person.profile_path, 'w92') || ''"
        :alt="person.name"
        class="w-12 h-12 rounded-md object-cover shrink-0"
        loading="lazy"
        decoding="async"
      />
      <div v-else class="w-12 h-12 rounded-md bg-surface-200 shrink-0 flex items-center justify-center text-muted text-xs font-medium">
        {{ initials(person.name) }}
      </div>
      <div class="min-w-0">
        <p class="text-secondary truncate">{{ person.name }}</p>
        <p v-if="person.character" class="text-gray-500 truncate text-xs">{{ person.character }}</p>
        <p v-else-if="person.job" class="text-gray-500 truncate text-xs">{{ person.job }}</p>
        <span v-if="episodeCount(person)" class="text-[11px] text-muted">{{ episodeCount(person) }} eps</span>
      </div>
    </div>
  </div>
  <p v-else class="text-sm text-muted">{{ emptyLabel }}</p>
</template>

<script setup lang="ts">
import { tmdbImageUrl } from '@/utils/images'
import type { Person } from '@/types/api'

withDefaults(defineProps<{
  people: Person[]
  emptyLabel?: string
}>(), { emptyLabel: 'No cast information available.' })

function episodeCount(person: Person): number | null {
  const count = person.total_episode_count
  if (typeof count === 'number' && count > 0) return count
  return null
}

function initials(name: string): string {
  return name.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()
}
</script>
