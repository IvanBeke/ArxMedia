<template>
  <div v-if="groups.length" class="card divide-y divide-surface-200 overflow-hidden">
    <div v-for="group in groups" :key="group.label" class="flex gap-4 px-4 py-3">
      <span class="w-12 shrink-0 text-sm text-muted">{{ group.label }}</span>
      <ul class="min-w-0 flex-1 space-y-2">
        <li v-for="item in group.items" :key="`${item.media_type}-${item.id}-${item.credit_id || item.character || item.job}`" class="text-sm min-w-0">
          <RouterLink :to="creditDetailLink(item)" :title="creditTitle(item)" class="text-brand-300 font-medium hover:text-brand-400 hover:underline transition-colors">
            {{ creditTitle(item) }}
          </RouterLink>
          <span v-if="episodeCount(item)" class="text-muted"> · {{ episodeCount(item) }} episodes</span>
          <span v-if="roleLine(item)" class="text-muted"> as {{ roleLine(item) }}</span>
        </li>
      </ul>
    </div>
  </div>
  <p v-else class="text-sm text-muted">{{ emptyLabel }}</p>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { creditDetailLink, creditRole, creditTitle, filterByMedia, groupCreditsByYear, type PersonMediaFilter } from '@/utils/person'
import type { PersonCredit } from '@/types/api'

const props = withDefaults(defineProps<{
  items?: PersonCredit[]
  mediaFilter?: PersonMediaFilter
  emptyLabel?: string
}>(), { items: () => [], mediaFilter: 'all', emptyLabel: 'No credits available.' })

const groups = computed(() => groupCreditsByYear(filterByMedia(props.items ?? [], props.mediaFilter)))

function episodeCount(item: PersonCredit): number | null {
  const count = item.episode_count
  return typeof count === 'number' && count > 1 ? count : null
}

function roleLine(item: PersonCredit): string {
  return creditRole(item)
}
</script>
