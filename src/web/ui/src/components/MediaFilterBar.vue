<template>
  <div class="card filter-controls mb-5 p-3 md:p-4 space-y-3" ref="rootRef">
    <div class="flex flex-col lg:flex-row gap-2">
      <div v-if="hasAdvancedFilters" class="relative">
        <button type="button" class="control-trigger" @click="toggleAdvanced">
          <span class="inline-flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18l-7 8v6l-4 2v-8L3 4z"/>
            </svg>
            <span>{{ advancedLabel }}</span>
            <span v-if="activeAdvancedCount" class="control-count">{{ activeAdvancedCount }}</span>
          </span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>

        <div v-if="advancedOpen" class="control-panel left-0 w-[20rem] max-w-[85vw] p-3 space-y-3">
          <div v-if="effectiveShowQuickFilterHasUpcoming || effectiveShowQuickFilterNewOnly || effectiveShowQuickFilterMissingRating" class="space-y-2">
            <p class="text-xs text-muted">Quick filters</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-if="effectiveShowQuickFilterHasUpcoming"
                type="button"
                class="chip-toggle"
                :data-on="staged.hasUpcoming ? 'true' : 'false'"
                @click="staged.hasUpcoming = !staged.hasUpcoming"
              >
                Has upcoming
              </button>
              <button
                v-if="effectiveShowQuickFilterNewOnly"
                type="button"
                class="chip-toggle"
                :data-on="staged.newOnly ? 'true' : 'false'"
                @click="staged.newOnly = !staged.newOnly"
              >
                New episodes
              </button>
              <button
                v-if="effectiveShowQuickFilterMissingRating"
                type="button"
                class="chip-toggle"
                :data-on="staged.missingRating ? 'true' : 'false'"
                @click="staged.missingRating = !staged.missingRating"
              >
                Missing rating
              </button>
            </div>
          </div>

          <div v-if="effectiveShowStatusFilter" class="space-y-2">
            <p class="text-xs text-muted">User status</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="statusOption in statusChipOptions"
                :key="statusOption.value"
                type="button"
                class="chip"
                :class="staged.statuses.includes(statusOption.value) ? 'chip-active' : ''"
                @click="toggleStagedArrayValue('statuses', statusOption.value)"
              >
                {{ statusOption.label }}
              </button>
            </div>
          </div>

          <div v-if="effectiveShowProviderStatusFilter" class="space-y-2">
            <p class="text-xs text-muted">Show status</p>
            <div class="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
              <button
                v-for="providerStatus in providerStatusOptions"
                :key="providerStatus"
                type="button"
                class="chip"
                :class="staged.providerStatuses.includes(providerStatus) ? 'chip-active' : ''"
                @click="toggleStagedArrayValue('providerStatuses', providerStatus)"
              >
                {{ providerStatus }}
              </button>
            </div>
          </div>

          <div v-if="effectiveShowGenreFilter" class="space-y-2">
            <p class="text-xs text-muted">Genres</p>
            <div class="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
              <button
                v-for="genre in resolvedGenreOptions"
                :key="genre"
                type="button"
                class="chip"
                :class="staged.genres.includes(genre) ? 'chip-active' : ''"
                @click="toggleStagedArrayValue('genres', genre)"
              >
                {{ genre }}
              </button>
            </div>
          </div>

          <div v-if="showMediaTypeFilter" class="space-y-2">
            <p class="text-xs text-muted">Media type</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="option in mediaTypeAdvancedOptions"
                :key="option.value"
                type="button"
                class="chip"
                :class="staged.mediaType === option.value ? 'chip-active' : ''"
                @click="toggleStagedMediaType(option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <div class="flex items-center justify-between pt-1 border-t border-surface-200">
            <button type="button" class="btn-ghost text-xs px-3 py-1.5" @click="clearAdvanced">Clear all</button>
            <button type="button" class="btn-primary text-xs px-3 py-1.5" @click="applyAdvanced">Apply</button>
          </div>
        </div>
      </div>

      <div v-if="showSearch" class="relative flex-1">
        <input
          v-model="draftSearch"
          type="text"
          class="input text-sm pl-10"
          :placeholder="searchPlaceholder"
          @keydown.enter="applySearch"
        >
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>

      <details v-if="showSort" class="relative control-menu">
        <summary class="control-trigger">
          <span class="inline-flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18M7 12h10M10 20h4"/>
            </svg>
            <span>Sorted by</span>
            <span class="text-primary">{{ currentSortLabel }}</span>
          </span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </summary>
        <div class="control-panel right-0 w-56">
          <button
            v-for="opt in resolvedSortOptions"
            :key="opt.value"
            type="button"
            class="control-option"
            @click="setSort(opt.value)"
          >
            <span>{{ opt.label }}</span>
            <span v-if="filters.sort === opt.value" class="text-brand-400">✓</span>
          </button>
        </div>
      </details>

      <button
        v-if="showDirection"
        type="button"
        class="control-trigger direction-trigger"
        :title="filters.direction === 'asc' ? 'Ascending' : 'Descending'"
        :aria-label="filters.direction === 'asc' ? 'Sorting ascending' : 'Sorting descending'"
        @click="setDirection(filters.direction === 'asc' ? 'desc' : 'asc')"
      >
        <span class="inline-flex items-center gap-1.5">
          <ArrowDownNarrowWide v-if="filters.direction === 'asc'" class="w-4 h-4" :stroke-width="2" aria-hidden="true" />
          <ArrowDownWideNarrow v-else class="w-4 h-4" :stroke-width="2" aria-hidden="true" />
          <span>{{ filters.direction }}</span>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { onClickOutside } from '@vueuse/core'
import { ArrowDownNarrowWide, ArrowDownWideNarrow } from '@lucide/vue'
import { mediaAPI } from '@/api'

const props = defineProps({
  showMediaTypeFilter: { type: Boolean, default: false },
  showStatusFilter: { type: Boolean, default: false },
  showProviderStatusFilter: { type: Boolean, default: false },
  showGenreFilter: { type: Boolean, default: true },
  showQuickFilterHasUpcoming: { type: Boolean, default: false },
  showQuickFilterNewOnly: { type: Boolean, default: false },
  showQuickFilterMissingRating: { type: Boolean, default: false },
  showSearch: { type: Boolean, default: true },
  showSort: { type: Boolean, default: true },
  showDirection: { type: Boolean, default: true },
  searchPlaceholder: { type: String, default: 'Search by title' },
  advancedLabel: { type: String, default: 'Advanced Filters' },
  mediaTypeContext: { type: String, default: 'all' },
  providerStatusOptions: { type: Array, default: () => [] },
  genreOptions: { type: Array, default: () => [] },
  syncUrl: { type: Boolean, default: true },
})

const emit = defineEmits(['change'])

const route = useRoute()
const router = useRouter()
const rootRef = ref(null)
const advancedOpen = ref(false)
const directionOverridden = ref(false)
const draftSearch = ref('')
const fetchedGenres = ref([])

const statusChipOptions = [
  { label: 'Watching', value: 'watching' },
  { label: 'Completed', value: 'watched' },
  { label: 'Dropped', value: 'dropped' },
]

const defaultDirectionsBySort = {
  added_at: 'desc',
  title: 'asc',
  rating: 'desc',
  vote_count: 'desc',
  runtime: 'asc',
  total_episodes: 'desc',
  media_type: 'asc',
  release_date: 'desc',
  first_air_date: 'desc',
  air_date: 'asc',
  time_left: 'asc',
  episodes_left: 'asc',
  last_watched: 'desc',
  progress_percent: 'desc',
}

const isProgressMode = computed(() => {
  return (
    props.showStatusFilter
    || props.showProviderStatusFilter
    || props.showGenreFilter
    || props.showQuickFilterHasUpcoming
    || props.showQuickFilterNewOnly
    || props.showQuickFilterMissingRating
  )
})

const defaultSort = computed(() => (isProgressMode.value ? 'time_left' : 'added_at'))

const filters = reactive({
  search: '',
  sort: defaultSort.value,
  direction: getDefaultDirection(defaultSort.value),
  mediaType: 'all',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
})

const staged = reactive({
  mediaType: 'all',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
})

const effectiveMediaType = computed(() => {
  if (props.showMediaTypeFilter) {
    return filters.mediaType || 'all'
  }
  return props.mediaTypeContext || 'all'
})

const advancedMediaType = computed(() => {
  if (props.showMediaTypeFilter && advancedOpen.value) {
    return staged.mediaType || 'all'
  }
  return effectiveMediaType.value
})

const isWatchlistRoute = computed(() => route.path.startsWith('/watchlist'))
const autoTvAdvancedEnabled = computed(() => advancedMediaType.value === 'tv' && !isWatchlistRoute.value)

const effectiveShowStatusFilter = computed(() => props.showStatusFilter || autoTvAdvancedEnabled.value)
const effectiveShowProviderStatusFilter = computed(() => props.showProviderStatusFilter || autoTvAdvancedEnabled.value)
const effectiveShowGenreFilter = computed(() => props.showGenreFilter)
const effectiveShowQuickFilterHasUpcoming = computed(() => props.showQuickFilterHasUpcoming || autoTvAdvancedEnabled.value)
const effectiveShowQuickFilterNewOnly = computed(() => props.showQuickFilterNewOnly || autoTvAdvancedEnabled.value)
const effectiveShowQuickFilterMissingRating = computed(() => props.showQuickFilterMissingRating || autoTvAdvancedEnabled.value)
const resolvedGenreOptions = computed(() => {
  const fromProps = props.genreOptions || []
  const fromApi = fetchedGenres.value || []
  return [...new Set([...fromProps, ...fromApi])].sort((a, b) => a.localeCompare(b))
})

const resolvedSortOptions = computed(() => {
  if (isProgressMode.value) {
    return [
      { label: 'Time left', value: 'time_left' },
      { label: 'Episodes left', value: 'episodes_left' },
      { label: 'Last watched', value: 'last_watched' },
      { label: 'Progress', value: 'progress_percent' },
      { label: 'Title', value: 'title' },
      { label: 'Air date', value: 'air_date' },
    ]
  }

  const dedup = new Map([
    ['added_at', { label: 'Date added', value: 'added_at' }],
    ['title', { label: 'Title', value: 'title' }],
    ['rating', { label: 'Rating', value: 'rating' }],
    ['vote_count', { label: 'Votes', value: 'vote_count' }],
    ['release_date', { label: 'Release date', value: 'release_date' }],
    ['runtime', { label: 'Runtime', value: 'runtime' }],
  ])

  if (effectiveMediaType.value === 'tv') {
    dedup.set('first_air_date', { label: 'First air date', value: 'first_air_date' })
    dedup.set('total_episodes', { label: 'Total episodes', value: 'total_episodes' })
  }

  return [...dedup.values()]
})

const mediaTypeAdvancedOptions = [
  { label: 'Movies', value: 'movie' },
  { label: 'Shows', value: 'tv' },
]

const hasAdvancedFilters = computed(() => {
  return (
    props.showMediaTypeFilter
    || effectiveShowStatusFilter.value
    || effectiveShowProviderStatusFilter.value
    || effectiveShowGenreFilter.value
    || effectiveShowQuickFilterHasUpcoming.value
    || effectiveShowQuickFilterNewOnly.value
    || effectiveShowQuickFilterMissingRating.value
  )
})

const currentSortLabel = computed(() => {
  return resolvedSortOptions.value.find((option) => option.value === filters.sort)?.label || 'Sort'
})

const activeAdvancedCount = computed(() => {
  let total = 0
  if (props.showMediaTypeFilter && filters.mediaType !== 'all') total += 1
  if (effectiveShowStatusFilter.value) total += filters.statuses.length
  if (effectiveShowProviderStatusFilter.value) total += filters.providerStatuses.length
  if (effectiveShowGenreFilter.value) total += filters.genres.length
  if (effectiveShowQuickFilterHasUpcoming.value && filters.hasUpcoming) total += 1
  if (effectiveShowQuickFilterNewOnly.value && filters.newOnly) total += 1
  if (effectiveShowQuickFilterMissingRating.value && filters.missingRating) total += 1
  return total
})

onClickOutside(rootRef, () => {
  if (!advancedOpen.value) return
  advancedOpen.value = false
  syncStagedFromApplied()
})

onMounted(async () => {
  try {
    const data = await mediaAPI.genres()
    fetchedGenres.value = Array.isArray(data)
      ? data.map((genre) => genre?.name).filter(Boolean)
      : []
  } catch {
    fetchedGenres.value = []
  }
})

watch(
  () => route.query,
  () => {
    const next = parseFromQuery(route.query)
    if (serializeFilters(next) === serializeFilters(filters)) {
      return
    }
    applyFiltersState(next)
    emitChange('hydrate')
  },
  { immediate: true, deep: true }
)

function getDefaultDirection(sortKey) {
  return defaultDirectionsBySort[sortKey] || 'asc'
}

function serializeFilters(value) {
  return JSON.stringify({
    search: value.search || '',
    sort: value.sort || defaultSort.value,
    direction: value.direction || getDefaultDirection(value.sort || defaultSort.value),
    mediaType: value.mediaType || 'all',
    statuses: [...(value.statuses || [])].sort(),
    providerStatuses: [...(value.providerStatuses || [])].sort(),
    genres: [...(value.genres || [])].sort(),
    hasUpcoming: Boolean(value.hasUpcoming),
    newOnly: Boolean(value.newOnly),
    missingRating: Boolean(value.missingRating),
  })
}

function applyFiltersState(next) {
  filters.search = next.search
  filters.sort = next.sort
  filters.direction = next.direction
  filters.mediaType = next.mediaType
  filters.statuses = [...next.statuses]
  filters.providerStatuses = [...next.providerStatuses]
  filters.genres = [...next.genres]
  filters.hasUpcoming = next.hasUpcoming
  filters.newOnly = next.newOnly
  filters.missingRating = next.missingRating
  draftSearch.value = next.search
  directionOverridden.value = next.directionOverridden
  syncStagedFromApplied()
}

function parseArray(queryValue) {
  if (Array.isArray(queryValue)) {
    return queryValue.map((entry) => String(entry)).filter(Boolean)
  }
  if (typeof queryValue === 'string' && queryValue) {
    return [queryValue]
  }
  return []
}

function parseFromQuery(query) {
  const next = {
    search: typeof query.search === 'string' ? query.search : '',
    sort: typeof query.sort === 'string' ? query.sort : defaultSort.value,
    direction: '',
    directionOverridden: false,
    mediaType: 'all',
    statuses: parseArray(query.status),
    providerStatuses: parseArray(query.provider_status),
    genres: parseArray(query.genres),
    hasUpcoming: query.has_upcoming === '1',
    newOnly: query.is_new === '1',
    missingRating: query.missing_rating === '1',
  }

  if (props.showMediaTypeFilter) {
    const mediaTypeValue = typeof query.media_type === 'string' ? query.media_type : 'all'
    next.mediaType = mediaTypeValue
  }

  if (query.direction === 'asc' || query.direction === 'desc') {
    next.direction = query.direction
    next.directionOverridden = true
  } else {
    next.direction = getDefaultDirection(next.sort)
  }

  if (!resolvedSortOptions.value.some((option) => option.value === next.sort)) {
    next.sort = defaultSort.value
    if (!next.directionOverridden) {
      next.direction = getDefaultDirection(next.sort)
    }
  }

  return next
}

function syncStagedFromApplied() {
  staged.mediaType = filters.mediaType
  staged.statuses = [...filters.statuses]
  staged.providerStatuses = [...filters.providerStatuses]
  staged.genres = [...filters.genres]
  staged.hasUpcoming = filters.hasUpcoming
  staged.newOnly = filters.newOnly
  staged.missingRating = filters.missingRating
}

function emitChange(source) {
  const payload = {
    search: filters.search,
    sort: filters.sort,
    direction: filters.direction,
    mediaType: filters.mediaType,
    statuses: [...filters.statuses],
    providerStatuses: [...filters.providerStatuses],
    genres: [...filters.genres],
    hasUpcoming: filters.hasUpcoming,
    newOnly: filters.newOnly,
    missingRating: filters.missingRating,
  }
  emit('change', { source, filters: payload })
}

function syncUrl() {
  if (!props.syncUrl) return

  const keys = ['search', 'sort', 'direction', 'media_type', 'status', 'provider_status', 'has_upcoming', 'is_new', 'missing_rating', 'genres']
  const nextQuery = { ...route.query }
  for (const key of keys) {
    delete nextQuery[key]
  }

  if (props.showSearch && filters.search) nextQuery.search = filters.search
  if (props.showSort && filters.sort !== defaultSort.value) nextQuery.sort = filters.sort
  if (props.showDirection && (directionOverridden.value || filters.direction !== getDefaultDirection(filters.sort))) {
    nextQuery.direction = filters.direction
  }
  if (props.showMediaTypeFilter && filters.mediaType !== 'all') nextQuery.media_type = filters.mediaType

  if (effectiveShowStatusFilter.value && filters.statuses.length) nextQuery.status = [...filters.statuses]
  if (effectiveShowProviderStatusFilter.value && filters.providerStatuses.length) nextQuery.provider_status = [...filters.providerStatuses]
  if (effectiveShowGenreFilter.value && filters.genres.length) nextQuery.genres = [...filters.genres]
  if (effectiveShowQuickFilterHasUpcoming.value && filters.hasUpcoming) nextQuery.has_upcoming = '1'
  if (effectiveShowQuickFilterNewOnly.value && filters.newOnly) nextQuery.is_new = '1'
  if (effectiveShowQuickFilterMissingRating.value && filters.missingRating) nextQuery.missing_rating = '1'

  if (JSON.stringify(nextQuery) !== JSON.stringify(route.query)) {
    router.replace({ query: nextQuery })
  }
}

function commitInteraction() {
  syncUrl()
  emitChange('interaction')
}

function toggleStagedArrayValue(key, value) {
  if (staged[key].includes(value)) {
    staged[key] = staged[key].filter((entry) => entry !== value)
  } else {
    staged[key] = [...staged[key], value]
  }
}

function toggleAdvanced() {
  if (advancedOpen.value) {
    advancedOpen.value = false
    syncStagedFromApplied()
    return
  }
  syncStagedFromApplied()
  advancedOpen.value = true
}

function applyAdvanced() {
  filters.mediaType = props.showMediaTypeFilter ? staged.mediaType : 'all'
  filters.statuses = effectiveShowStatusFilter.value ? [...staged.statuses] : []
  filters.providerStatuses = effectiveShowProviderStatusFilter.value ? [...staged.providerStatuses] : []
  filters.genres = effectiveShowGenreFilter.value ? [...staged.genres] : []
  filters.hasUpcoming = effectiveShowQuickFilterHasUpcoming.value ? staged.hasUpcoming : false
  filters.newOnly = effectiveShowQuickFilterNewOnly.value ? staged.newOnly : false
  filters.missingRating = effectiveShowQuickFilterMissingRating.value ? staged.missingRating : false
  advancedOpen.value = false
  commitInteraction()
}

function clearAdvanced() {
  staged.mediaType = 'all'
  staged.statuses = []
  staged.providerStatuses = []
  staged.genres = []
  staged.hasUpcoming = false
  staged.newOnly = false
  staged.missingRating = false
  applyAdvanced()
}

function applySearch() {
  filters.search = draftSearch.value.trim()
  commitInteraction()
}

function setSort(nextSort) {
  filters.sort = nextSort
  if (!directionOverridden.value) {
    filters.direction = getDefaultDirection(nextSort)
  }
  commitInteraction()
}

watch(
  [resolvedSortOptions, defaultSort],
  () => {
    if (resolvedSortOptions.value.some((option) => option.value === filters.sort)) {
      return
    }
    filters.sort = defaultSort.value
    if (!directionOverridden.value) {
      filters.direction = getDefaultDirection(filters.sort)
    }
    commitInteraction()
  },
  { deep: true }
)

function setDirection(nextDirection) {
  filters.direction = nextDirection
  directionOverridden.value = true
  commitInteraction()
}

function toggleStagedMediaType(nextType) {
  if (staged.mediaType === nextType) {
    staged.mediaType = 'all'
    return
  }
  staged.mediaType = nextType
}
</script>

<style scoped>
.filter-controls {
  position: relative;
  z-index: 30;
  overflow: visible;
  background: linear-gradient(180deg, color-mix(in srgb, var(--bg-surface-100) 92%, white 8%), var(--bg-surface-100));
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
</style>
