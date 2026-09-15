<template>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <RouterLink
      v-for="person in people"
      :key="`person-${person.id}`"
      :to="`/people/${person.id}`"
      class="card p-3 hover:bg-surface-200/40 transition-colors"
    >
      <div class="flex items-center gap-2.5 min-w-0">
        <img
          v-if="person.profile_path"
          :src="tmdbImageUrl(person.profile_path, 'w185') || ''"
          :alt="`${person.name} profile photo`"
          class="w-8 h-8 rounded-full object-cover border border-surface-200 flex-shrink-0"
          loading="lazy"
          decoding="async"
        />
        <div
          v-else
          class="w-8 h-8 rounded-full bg-brand-500/20 border border-brand-500/30 text-brand-300 text-xs font-semibold flex items-center justify-center flex-shrink-0"
        >
          {{ initial(person.name) }}
        </div>
        <span class="text-primary text-sm font-semibold hover:text-brand-400 truncate">
          {{ person.name }}
        </span>
      </div>

      <p v-if="person.known_for_department" class="text-[11px] text-muted mt-2 truncate">{{ person.known_for_department }}</p>

      <p v-if="knownForTitles(person)" class="text-[11px] text-muted mt-1 truncate" :title="knownForTitles(person)">
        {{ knownForTitles(person) }}
      </p>
    </RouterLink>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { tmdbImageUrl } from '@/utils/images'
import type { PersonSearchResult } from '@/types/api'

withDefaults(defineProps<{
  people?: PersonSearchResult[]
}>(), { people: () => [] })

function initial(name: string): string {
  return (name.trim()[0] || '?').toUpperCase()
}

function knownForTitles(person: PersonSearchResult): string {
  return (person.known_for ?? [])
    .map((item) => item.title || item.name || '')
    .filter((title) => title.length > 0)
    .slice(0, 3)
    .join(', ')
}
</script>
