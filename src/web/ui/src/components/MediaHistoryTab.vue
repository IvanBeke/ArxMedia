<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 class="text-primary font-medium">{{ t('history_tab_title') }}</h3>
        <p v-if="count > 0" class="text-sm text-muted mt-1">
          {{ count }} {{ count === 1 ? t('history_entry_one') : t('history_entry_many') }}
        </p>
      </div>
      <RouterLink :to="fullHistoryLink" class="text-sm text-brand-400 hover:text-brand-300">
        {{ t('history_view_full') }}
      </RouterLink>
    </div>

    <Transition name="fade">
      <div v-if="deleteError" role="alert" class="px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ deleteError }}
      </div>
    </Transition>

    <div v-if="loading" class="grid max-w-6xl grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4" :aria-label="t('history_loading')">
      <div v-for="n in 6" :key="n" class="aspect-[2/3] skeleton rounded-lg"></div>
    </div>

    <div v-else-if="errorMessage" class="card p-8 text-center" role="alert">
      <p class="text-secondary">{{ errorMessage }}</p>
      <button type="button" class="btn-ghost mt-4" @click="loadHistory">{{ t('action_try_again') }}</button>
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
      {{ t('history_empty_item') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { trackingAPI } from '@/api'
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import { getApiErrorMessage } from '@/utils/errors'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { useI18n } from '@/i18n'
import { getRemoveHistoryConfirmText, useHistoryDelete } from '@/composables/useHistoryDelete'
import { historyItemQuery, historyItemRoute, type HistoryItemFilter } from '@/utils/historyFilters'
import { normalizePagedResponse } from '@/utils/pagination'
import { getWatchEntryLink, getWatchEntryTitleLink } from '@/utils/watchEntryLinks'
import type { WatchEntry } from '@/types/api'

const props = defineProps<{
  filter: HistoryItemFilter
}>()

const entries = ref<WatchEntry[]>([])
const { t } = useI18n()
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

const { errorMsg: deleteError, showError: showDeleteError } = useFlashMessages()
const { deletingEntryId, deleteEntry } = useHistoryDelete({
  onDeleted: async () => {
    await loadHistory()
  },
  onError: showDeleteError,
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
    errorMessage.value = getApiErrorMessage(error, t('history_load_failed'))
  } finally {
    if (currentRequestId === requestId) {
      loading.value = false
    }
  }
}

watch(historyParams, loadHistory, { immediate: true })
</script>
