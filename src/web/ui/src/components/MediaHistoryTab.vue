<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 class="text-primary font-medium">Watch history</h3>
        <p v-if="count > 0" class="text-sm text-muted mt-1">
          {{ count }} {{ count === 1 ? 'entry' : 'entries' }}
        </p>
      </div>
      <RouterLink :to="fullHistoryLink" class="text-sm text-brand-400 hover:text-brand-300">
        View full history →
      </RouterLink>
    </div>

    <div v-if="loading" class="grid max-w-6xl grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4" aria-label="Loading watch history">
      <div v-for="n in 6" :key="n" class="aspect-[2/3] skeleton rounded-lg"></div>
    </div>

    <div v-else-if="errorMessage" class="card p-8 text-center" role="alert">
      <p class="text-secondary">{{ errorMessage }}</p>
      <button type="button" class="btn-ghost mt-4" @click="loadHistory">Try again</button>
    </div>

    <div v-else-if="entries.length" class="grid max-w-6xl grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      <div v-for="entry in entries" :key="entry.id" class="group relative">
        <HistoryMediaCard
          :entry="entry"
          :link-to="getWatchEntryLink(entry)"
          :title-link-to="getWatchEntryTitleLink(entry)"
          :show-remove-action="true"
          :remove-loading="deletingEntryId === entry.id"
          :remove-confirm-text="getRemoveHistoryConfirmText(entry)"
          @action:history-remove="deleteEntry"
        />
      </div>
    </div>

    <div v-else class="card p-8 text-center text-muted" aria-live="polite">
      No watch history for this item yet.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { trackingAPI } from '@/api'
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import { getApiErrorMessage } from '@/utils/errors'
import { getRemoveHistoryConfirmText, useHistoryDelete } from '@/composables/useHistoryDelete'
import { historyItemQuery, historyItemRoute, type HistoryItemFilter } from '@/utils/historyFilters'
import { normalizePagedResponse } from '@/utils/pagination'
import { getWatchEntryLink, getWatchEntryTitleLink } from '@/utils/watchEntryLinks'
import type { WatchEntry } from '@/types/api'

const props = defineProps<{
  filter: HistoryItemFilter
}>()

const entries = ref<WatchEntry[]>([])
const count = ref(0)
const loading = ref(true)
const errorMessage = ref('')
let requestId = 0

const historyParams = computed(() => ({
  ...historyItemQuery(props.filter),
  order: 'newest',
  page: 1,
}))

const fullHistoryLink = computed(() => historyItemRoute(props.filter))

const { deletingEntryId, deleteEntry } = useHistoryDelete({
  onDeleted: async () => {
    await loadHistory()
  },
})

async function loadHistory() {
  const currentRequestId = ++requestId
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await trackingAPI.getHistory(historyParams.value)
    if (currentRequestId !== requestId) return

    const paged = normalizePagedResponse<WatchEntry>(response)
    entries.value = paged.items.slice(0, 20)
    count.value = paged.count
  } catch (error) {
    if (currentRequestId !== requestId) return
    entries.value = []
    count.value = 0
    errorMessage.value = getApiErrorMessage(error, 'Could not load watch history.')
    console.error('Failed to load media history', error)
  } finally {
    if (currentRequestId === requestId) {
      loading.value = false
    }
  }
}

watch(historyParams, loadHistory, { immediate: true })
</script>
