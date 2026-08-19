<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex flex-wrap items-end justify-between gap-3 mb-6">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">Progress</h1>
        <p class="text-muted text-sm">Track started shows and decide what to watch next.</p>
      </div>
      <div class="inline-flex items-center gap-2 rounded-full border border-surface-200 bg-surface-100 px-3 py-1 text-xs text-secondary">
        <span class="h-1.5 w-1.5 rounded-full bg-brand-500"></span>
        <span>{{ count }} shows | {{ watchedTimeLabel }}</span>
      </div>
    </div>

    <MediaFilterBar
      :show-media-type-filter="false"
      :show-status-filter="true"
      :show-provider-status-filter="true"
      :show-genre-filter="true"
      :show-quick-filter-has-upcoming="true"
      :show-quick-filter-new-only="true"
      :show-quick-filter-missing-rating="true"
      :show-search="true"
      :show-sort="true"
      :show-direction="true"
      search-placeholder="Search by show title"
      media-type-context="tv"
      :provider-status-options="availableProviderStatuses"
      :genre-options="availableGenres"
      :sync-url="true"
      @change="onFilterBarChange"
    />

    <div v-if="loading" class="space-y-3">
      <div v-for="n in 8" :key="n" class="h-28 rounded-lg skeleton"></div>
    </div>

    <div v-else-if="rows.length" class="space-y-3 md:space-y-4">
      <ProgressRow
        v-for="item in rows"
        :key="item.tmdb_id"
        :item="item"
        :row-busy-id="rowBusyId"
        @drop="drop"
        @open-rate="openRateModal"
        @open-add-to-list="openAddToListModal"
      />

      <PaginationControls
        :current-page="currentPage"
        :total-pages="totalPages"
        :max-visible-pages="10"
        :disabled="loading"
        @go="goToPage"
      />
    </div>

    <div v-else class="card p-10 text-center">
      <p class="text-sm text-muted mb-3">No started shows match your current filters.</p>
      <button class="btn-primary text-sm" @click="resetFilters">Clear filters</button>
    </div>

    <p v-if="errorMsg" class="mt-3 text-sm text-red-400">{{ errorMsg }}</p>

    <dialog
      ref="rateDialog"
      closedby="any"
      class="progress-dialog w-full max-w-md rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
      aria-labelledby="progress-rate-title"
      @click="onDialogClick($event, rateDialog)"
      @close="onRateDialogClose"
    >
      <div class="p-5 md:p-6">
        <div class="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="progress-rate-title" class="text-lg font-display text-primary font-semibold">Rate show</h2>
            <p class="text-xs text-muted mt-1">{{ activeRow?.show_name || 'Select your score' }}</p>
          </div>
          <button type="button" class="text-muted hover:text-primary" @click="closeRateModal">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="rounded-lg border border-surface-200 bg-surface px-3 py-3">
          <p class="text-xs text-muted mb-2">Your rating</p>
          <StarRating v-model="modalRating" @update:modelValue="submitRateFromModal" />
        </div>

        <p v-if="modalBusy" class="mt-3 text-xs text-muted">Saving rating...</p>
      </div>
    </dialog>

    <dialog
      ref="addToListDialog"
      closedby="any"
      class="progress-dialog w-full max-w-lg rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
      aria-labelledby="progress-list-title"
      @click="onDialogClick($event, addToListDialog)"
      @close="onAddToListDialogClose"
    >
      <div class="p-5 md:p-6">
        <div class="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="progress-list-title" class="text-lg font-display text-primary font-semibold">Add to list</h2>
            <p class="text-xs text-muted mt-1">{{ activeRow?.show_name || 'Select a list' }}</p>
          </div>
          <button type="button" class="text-muted hover:text-primary" @click="closeAddToListModal">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="rounded-lg border border-surface-200 bg-surface p-3">
          <AddToListPopover
            v-if="activeRow"
            :media-type="MEDIA_TYPE.TV"
            :tmdb-id="activeRow.tmdb_id"
            :start-open="true"
            :modal-mode="true"
            @added="onModalListAdded"
          />
        </div>
      </div>
    </dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { trackingAPI } from '@/api'
import AddToListPopover from '@/components/AddToListPopover.vue'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import { getApiErrorMessage } from '@/utils/errors'
import { formatHoursMinutes } from '@/utils/progress'
import { MEDIA_TYPE } from '@/constants/tracking'
import PaginationControls from '@/components/PaginationControls.vue'
import ProgressRow from '@/components/ProgressRow.vue'
import StarRating from '@/components/StarRating.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const rows = ref([])
const errorMsg = ref('')
const rowBusyId = ref(null)

const appliedFilters = ref({
  search: '',
  sort: 'time_left',
  direction: 'asc',
  mediaType: 'all',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
})

const availableGenres = ref([])
const availableProviderStatuses = ref([])

const count = ref(0)
const totalWatchedMinutes = ref(0)
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = ref(20)
const activeRow = ref(null)
const rateDialog = ref(null)
const addToListDialog = ref(null)
const modalRating = ref(0)
const modalBusy = ref(false)

const watchedTimeLabel = computed(() => {
  return formatHoursMinutes(totalWatchedMinutes.value)
})

function onFilterBarChange(payload) {
  const next = payload?.filters
  if (!next) return

  const didChange = JSON.stringify(appliedFilters.value) !== JSON.stringify(next)
  appliedFilters.value = next

  if (didChange && payload?.source === 'interaction') {
    currentPage.value = 1
  }
}

function goToPage(page) {
  if (!Number.isInteger(page) || page < 1 || page > totalPages.value || page === currentPage.value || loading.value) {
    return
  }
  currentPage.value = page
}

function buildParams() {
  const filterState = appliedFilters.value
  return {
    page: currentPage.value,
    sort: filterState.sort,
    direction: filterState.direction,
    ...(filterState.search ? { search: filterState.search } : {}),
    ...(filterState.statuses.length ? { status: filterState.statuses } : {}),
    ...(filterState.providerStatuses.length ? { provider_status: filterState.providerStatuses } : {}),
    ...(filterState.hasUpcoming ? { has_upcoming: true } : {}),
    ...(filterState.newOnly ? { is_new: true } : {}),
    ...(filterState.missingRating ? { missing_rating: true } : {}),
    ...(filterState.genres.length ? { genres: filterState.genres } : {}),
  }
}

function parsePage(value) {
  const page = Number.parseInt(String(value || '1'), 10)
  return Number.isInteger(page) && page > 0 ? page : 1
}

function syncPageQuery() {
  const nextQuery = {
    ...route.query,
    page: String(currentPage.value),
  }
  if (JSON.stringify(nextQuery) !== JSON.stringify(route.query)) {
    router.replace({ query: nextQuery })
  }
}

async function loadProgress() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await trackingAPI.getProgress(buildParams())
    rows.value = data?.results || []
    availableGenres.value = data?.available_genres || []
    availableProviderStatuses.value = data?.available_provider_statuses || []
    count.value = Number.isFinite(data?.count) ? data.count : rows.value.length
    totalWatchedMinutes.value = Number.isFinite(data?.total_watched_minutes) ? data.total_watched_minutes : 0
    if (Array.isArray(data?.results) && data.results.length > 0) {
      pageSize.value = data.results.length
    }
    totalPages.value = Math.max(1, Math.ceil(count.value / pageSize.value))
  } catch (error) {
    rows.value = []
    count.value = 0
    totalWatchedMinutes.value = 0
    totalPages.value = 1
    errorMsg.value = getApiErrorMessage(error, 'Could not load progress.')
  } finally {
    loading.value = false
  }
}

function onDialogClick(event, dialogRef) {
  const dialog = dialogRef?.value
  if (!dialog || event.target !== dialog) {
    return
  }
  const rect = dialog.getBoundingClientRect()
  const inDialog = (
    event.clientX >= rect.left &&
    event.clientX <= rect.right &&
    event.clientY >= rect.top &&
    event.clientY <= rect.bottom
  )
  if (!inDialog) {
    dialog.close()
  }
}

function openRateModal(item) {
  activeRow.value = item
  modalRating.value = Number(item?.user_rating) || 0
  rateDialog.value?.showModal()
}

function closeRateModal() {
  rateDialog.value?.close()
}

function onRateDialogClose() {
  modalBusy.value = false
  modalRating.value = 0
  if (!addToListDialog.value?.open) {
    activeRow.value = null
  }
}

async function submitRateFromModal(score) {
  if (!activeRow.value) return
  if (!Number.isInteger(score) || score < 1 || score > 10 || modalBusy.value) {
    return
  }
  modalBusy.value = true
  try {
    await rate(activeRow.value.tmdb_id, score)
    closeRateModal()
  } finally {
    modalBusy.value = false
  }
}

function openAddToListModal(item) {
  activeRow.value = item
  addToListDialog.value?.showModal()
}

function closeAddToListModal() {
  addToListDialog.value?.close()
}

function onAddToListDialogClose() {
  if (!rateDialog.value?.open) {
    activeRow.value = null
  }
}

async function onModalListAdded() {
  await loadProgress()
  closeAddToListModal()
}

async function drop(tmdbId) {
  if (rowBusyId.value) return
  rowBusyId.value = tmdbId
  try {
    await trackingAPI.dropShow({ tmdb_id: tmdbId })
    await loadProgress()
  } catch (error) {
    errorMsg.value = getApiErrorMessage(error, 'Could not drop show.')
  } finally {
    rowBusyId.value = null
  }
}

async function rate(tmdbId, score) {
  if (!Number.isInteger(score) || score < 1 || score > 10) {
    return
  }
  try {
    await trackingAPI.rate({ media_type: MEDIA_TYPE.TV, tmdb_id: tmdbId, score })
    await loadProgress()
  } catch (error) {
    errorMsg.value = getApiErrorMessage(error, 'Could not submit rating.')
  }
}

function resetFilters() {
  const nextQuery = { ...route.query, page: '1' }
  delete nextQuery.search
  delete nextQuery.sort
  delete nextQuery.direction
  delete nextQuery.status
  delete nextQuery.provider_status
  delete nextQuery.has_upcoming
  delete nextQuery.is_new
  delete nextQuery.missing_rating
  delete nextQuery.genres
  router.replace({ query: nextQuery })
}

watch(
  [appliedFilters, currentPage],
  async () => {
    syncPageQuery()
    await loadProgress()
  },
  { deep: true }
)

watch(
  () => route.query.page,
  async () => {
    currentPage.value = parsePage(route.query.page)
    await loadProgress()
  }
)

onMounted(async () => {
  currentPage.value = parsePage(route.query.page)
  await loadProgress()
})
</script>

<style scoped>
.progress-dialog::backdrop {
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(2px);
}

.progress-dialog {
  margin: auto;
}
</style>
