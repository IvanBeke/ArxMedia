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

    <div class="card progress-controls mb-5 p-3 md:p-4 space-y-3">
      <div class="flex flex-col lg:flex-row gap-2">
        <div class="relative" ref="advancedFiltersRef">
          <button type="button" class="control-trigger" @click="toggleAdvancedFilters">
            <span class="inline-flex items-center gap-1.5">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18l-7 8v6l-4 2v-8L3 4z"/>
              </svg>
              <span>Advanced Filters</span>
              <span v-if="activeFilterCount" class="control-count">{{ activeFilterCount }}</span>
            </span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </button>

          <div v-if="showAdvancedFilters" class="control-panel left-0 w-[20rem] max-w-[85vw] p-3 space-y-3">
            <div class="space-y-2">
              <p class="text-xs text-muted">Quick filters</p>
              <div class="flex flex-wrap gap-2">
                <button type="button" class="chip-toggle" :data-on="staged.hasUpcoming ? 'true' : 'false'" @click="staged.hasUpcoming = !staged.hasUpcoming">
                  Has upcoming
                </button>
                <button type="button" class="chip-toggle" :data-on="staged.newOnly ? 'true' : 'false'" @click="staged.newOnly = !staged.newOnly">
                  New episodes
                </button>
                <button type="button" class="chip-toggle" :data-on="staged.missingRating ? 'true' : 'false'" @click="staged.missingRating = !staged.missingRating">
                  Missing rating
                </button>
              </div>
            </div>

            <div class="space-y-2">
              <p class="text-xs text-muted">User status</p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="chip in statusChips"
                  :key="chip.value"
                  class="chip"
                  :class="staged.statuses.includes(chip.value) ? 'chip-active' : ''"
                  @click="setStagedStatus(chip.value)"
                >
                  {{ chip.label }}
                </button>
              </div>
            </div>

            <div class="space-y-2">
              <p class="text-xs text-muted">Show status</p>
              <div class="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
                <button
                  v-for="providerStatus in availableProviderStatuses"
                  :key="providerStatus"
                  type="button"
                  class="chip"
                  :class="staged.providerStatuses.includes(providerStatus) ? 'chip-active' : ''"
                  @click="toggleStagedProviderStatus(providerStatus)"
                >
                  {{ providerStatus }}
                </button>
              </div>
            </div>

            <div class="space-y-2">
              <p class="text-xs text-muted">Genres</p>
              <div class="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
                <button
                  v-for="genre in availableGenres"
                  :key="genre"
                  type="button"
                  class="chip"
                  :class="staged.genres.includes(genre) ? 'chip-active' : ''"
                  @click="toggleStagedGenre(genre)"
                >
                  {{ genre }}
                </button>
              </div>
            </div>

            <div class="flex items-center justify-between pt-1 border-t border-surface-200">
              <button type="button" class="btn-ghost text-xs px-3 py-1.5" @click="clearStagedFilters">Clear all</button>
              <button type="button" class="btn-primary text-xs px-3 py-1.5" @click="applyAdvancedFilters">Apply</button>
            </div>
          </div>
        </div>

        <div class="relative flex-1">
          <input
            v-model="searchInput"
            type="text"
            class="input text-sm pl-10"
            placeholder="Search by show title"
            @keydown.enter="applySearch"
          >
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
        </div>

        <details class="relative control-menu">
          <summary class="control-trigger">
            <span class="inline-flex items-center gap-1.5">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18M7 12h10M10 20h4"/>
              </svg>
              <span>Sorted by</span>
              <span class="text-primary">{{ sortLabel }}</span>
            </span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="control-panel right-0 w-56">
            <button v-for="opt in sortOptions" :key="opt.value" type="button" class="control-option" @click="selectSort(opt.value)">
              <span>{{ opt.label }}</span>
              <span v-if="sort === opt.value" class="text-brand-400">✓</span>
            </button>
          </div>
        </details>

        <button
          type="button"
          class="control-trigger direction-trigger"
          :title="direction === 'asc' ? 'Ascending' : 'Descending'"
          :aria-label="direction === 'asc' ? 'Sorting ascending' : 'Sorting descending'"
          @click="toggleDirection"
        >
          <span class="inline-flex items-center gap-1.5">
            <ArrowDownNarrowWide v-if="direction === 'asc'" class="w-4 h-4" :stroke-width="2" aria-hidden="true" />
            <ArrowDownWideNarrow v-else class="w-4 h-4" :stroke-width="2" aria-hidden="true" />
            <span>{{ direction }}</span>
          </span>
        </button>
      </div>
    </div>

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
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { onClickOutside } from '@vueuse/core'
import { ArrowDownNarrowWide, ArrowDownWideNarrow } from '@lucide/vue'
import { trackingAPI } from '@/api'
import AddToListPopover from '@/components/AddToListPopover.vue'
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

const searchInput = ref('')
const search = ref('')
const statuses = ref([])
const providerStatuses = ref([])
const sort = ref('time_left')
const direction = ref('asc')
const hasUpcoming = ref(false)
const newOnly = ref(false)
const missingRating = ref(false)
const selectedGenres = ref([])
const showAdvancedFilters = ref(false)
const advancedFiltersRef = ref(null)
const staged = ref({
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

const statusChips = [
  { label: 'Watching', value: 'watching' },
  { label: 'Completed', value: 'watched' },
  { label: 'Dropped', value: 'dropped' },
]

const sortOptions = [
  { label: 'Time left', value: 'time_left' },
  { label: 'Episodes left', value: 'episodes_left' },
  { label: 'Last watched', value: 'last_watched' },
  { label: 'Progress', value: 'progress_percent' },
  { label: 'Title', value: 'title' },
  { label: 'Air date', value: 'air_date' },
]

const sortLabel = computed(() => sortOptions.find((entry) => entry.value === sort.value)?.label || 'Time left')

const activeFilterCount = computed(() => {
  let total = 0
  total += statuses.value.length
  total += providerStatuses.value.length
  total += selectedGenres.value.length
  if (hasUpcoming.value) total += 1
  if (newOnly.value) total += 1
  if (missingRating.value) total += 1
  return total
})

function resetStagedFromCommitted() {
  staged.value = {
    statuses: [...statuses.value],
    providerStatuses: [...providerStatuses.value],
    genres: [...selectedGenres.value],
    hasUpcoming: hasUpcoming.value,
    newOnly: newOnly.value,
    missingRating: missingRating.value,
  }
}

function toggleAdvancedFilters() {
  if (showAdvancedFilters.value) {
    showAdvancedFilters.value = false
    resetStagedFromCommitted()
    return
  }
  resetStagedFromCommitted()
  showAdvancedFilters.value = true
}

function setStagedStatus(nextStatus) {
  if (staged.value.statuses.includes(nextStatus)) {
    staged.value.statuses = staged.value.statuses.filter((statusValue) => statusValue !== nextStatus)
  } else {
    staged.value.statuses = [...staged.value.statuses, nextStatus]
  }
}

function toggleStagedProviderStatus(nextStatus) {
  if (staged.value.providerStatuses.includes(nextStatus)) {
    staged.value.providerStatuses = staged.value.providerStatuses.filter((statusValue) => statusValue !== nextStatus)
  } else {
    staged.value.providerStatuses = [...staged.value.providerStatuses, nextStatus]
  }
}

function toggleStagedGenre(nextGenre) {
  if (staged.value.genres.includes(nextGenre)) {
    staged.value.genres = staged.value.genres.filter((genreValue) => genreValue !== nextGenre)
  } else {
    staged.value.genres = [...staged.value.genres, nextGenre]
  }
}

function clearStagedFilters() {
  staged.value = {
    statuses: [],
    providerStatuses: [],
    genres: [],
    hasUpcoming: false,
    newOnly: false,
    missingRating: false,
  }
}

function applyAdvancedFilters() {
  statuses.value = [...staged.value.statuses]
  providerStatuses.value = [...staged.value.providerStatuses]
  selectedGenres.value = [...staged.value.genres]
  hasUpcoming.value = staged.value.hasUpcoming
  newOnly.value = staged.value.newOnly
  missingRating.value = staged.value.missingRating
  currentPage.value = 1
  showAdvancedFilters.value = false
}

onClickOutside(advancedFiltersRef, () => {
  if (!showAdvancedFilters.value) return
  showAdvancedFilters.value = false
  resetStagedFromCommitted()
})

function selectSort(value) {
  sort.value = value
  currentPage.value = 1
}

function toggleDirection() {
  direction.value = direction.value === 'asc' ? 'desc' : 'asc'
  currentPage.value = 1
}

function applySearch() {
  search.value = searchInput.value.trim()
  currentPage.value = 1
}

function goToPage(page) {
  if (!Number.isInteger(page) || page < 1 || page > totalPages.value || page === currentPage.value || loading.value) {
    return
  }
  currentPage.value = page
}

function buildParams() {
  return {
    page: currentPage.value,
    sort: sort.value,
    direction: direction.value,
    ...(search.value ? { search: search.value } : {}),
    ...(statuses.value.length ? { status: statuses.value } : {}),
    ...(providerStatuses.value.length ? { provider_status: providerStatuses.value } : {}),
    ...(hasUpcoming.value ? { has_upcoming: true } : {}),
    ...(newOnly.value ? { is_new: true } : {}),
    ...(missingRating.value ? { missing_rating: true } : {}),
    ...(selectedGenres.value.length ? { genres: selectedGenres.value } : {}),
  }
}

function syncUrlWithState() {
  const nextQuery = {
    page: String(currentPage.value),
    sort: sort.value,
    direction: direction.value,
  }
  if (search.value) nextQuery.search = search.value
  if (statuses.value.length) nextQuery.status = statuses.value
  if (providerStatuses.value.length) nextQuery.provider_status = providerStatuses.value
  if (hasUpcoming.value) nextQuery.has_upcoming = '1'
  if (newOnly.value) nextQuery.is_new = '1'
  if (missingRating.value) nextQuery.missing_rating = '1'
  if (selectedGenres.value.length) nextQuery.genres = selectedGenres.value
  router.replace({ query: nextQuery })
}

function hydrateFromQuery() {
  const query = route.query
  const parseArray = (value) => {
    if (Array.isArray(value)) return value.filter(Boolean)
    if (typeof value === 'string' && value) return [value]
    return []
  }
  search.value = typeof query.search === 'string' ? query.search : ''
  searchInput.value = search.value
  statuses.value = parseArray(query.status)
  providerStatuses.value = parseArray(query.provider_status)
  sort.value = typeof query.sort === 'string' ? query.sort : 'time_left'
  direction.value = query.direction === 'desc' ? 'desc' : 'asc'
  hasUpcoming.value = query.has_upcoming === '1'
  newOnly.value = query.is_new === '1'
  missingRating.value = query.missing_rating === '1'
  selectedGenres.value = parseArray(query.genres)
  const page = Number.parseInt(String(query.page || '1'), 10)
  currentPage.value = Number.isInteger(page) && page > 0 ? page : 1
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
  searchInput.value = ''
  search.value = ''
  statuses.value = []
  providerStatuses.value = []
  sort.value = 'time_left'
  direction.value = 'asc'
  hasUpcoming.value = false
  newOnly.value = false
  missingRating.value = false
  selectedGenres.value = []
  currentPage.value = 1
}

watch(
  [search, sort, direction, statuses, providerStatuses, hasUpcoming, newOnly, missingRating, selectedGenres, currentPage],
  async () => {
    syncUrlWithState()
    await loadProgress()
  },
  { deep: true }
)

watch(
  () => route.query,
  async () => {
    hydrateFromQuery()
    await loadProgress()
  },
  { immediate: true }
)
</script>

<style scoped>
.progress-controls {
  position: relative;
  z-index: 30;
  overflow: visible;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-surface-100) 92%, white 8%), var(--bg-surface-100));
}

.chip {
  border: 1px solid var(--filter-chip-border);
  background: var(--filter-chip-bg);
  color: var(--filter-chip-text);
  border-radius: 9999px;
  font-size: 0.75rem;
  line-height: 1;
  padding: 0.45rem 0.75rem;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
}

.chip:hover {
  background: var(--filter-chip-bg-hover);
  color: var(--filter-chip-text-hover);
}

.chip-active {
  background: var(--filter-chip-active-bg);
  color: var(--filter-chip-active-text);
  border-color: var(--filter-chip-active-border);
}

.chip-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--filter-chip-border);
  background: var(--filter-chip-bg);
  color: var(--filter-chip-text);
  border-radius: 9999px;
  font-size: 0.75rem;
  line-height: 1;
  padding: 0.45rem 0.75rem;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s;
}

.chip-toggle[data-on='true'] {
  background: var(--filter-chip-active-bg);
  color: var(--filter-chip-active-text);
  border-color: var(--filter-chip-active-border);
}

.chip-toggle:hover {
  background: var(--filter-chip-bg-hover);
  color: var(--filter-chip-text-hover);
}

.control-menu {
  position: relative;
}

.control-menu[open] {
  z-index: 80;
}

.control-trigger {
  list-style: none;
  min-height: 2.5rem;
  border: 1px solid var(--bg-surface-200);
  background: var(--bg-surface-100);
  border-radius: 0.625rem;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  min-width: 11rem;
  cursor: pointer;
}

.direction-trigger {
  min-width: 6.5rem;
  justify-content: center;
  text-transform: lowercase;
}

.control-trigger::-webkit-details-marker {
  display: none;
}

.control-trigger-sm {
  min-height: 2rem;
  font-size: 0.75rem;
  border-radius: 9999px;
  min-width: auto;
}

.control-count {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 9999px;
  display: inline-grid;
  place-items: center;
  font-size: 0.6875rem;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--filter-chip-active-text);
  background: var(--filter-chip-active-bg);
  border: 1px solid var(--filter-chip-active-border);
}

.control-panel {
  position: absolute;
  z-index: 60;
  margin-top: 0.35rem;
  border-radius: 0.75rem;
  border: 1px solid var(--bg-surface-200);
  background: var(--bg-surface-100);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
}

.control-option {
  width: 100%;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  font-size: 0.8125rem;
  border-radius: 0.5rem;
  padding: 0.5rem 0.6rem;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
}

.control-option:hover {
  background: var(--bg-surface-200);
  color: var(--text-primary);
}

.progress-dialog::backdrop {
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(2px);
}

.progress-dialog {
  margin: auto;
}
</style>
