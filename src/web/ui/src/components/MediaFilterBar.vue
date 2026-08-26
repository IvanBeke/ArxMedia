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
          <div v-if="showQuickFilterHasUpcomingEffective || showQuickFilterNewOnlyEffective || showQuickFilterMissingRatingEffective || showQuickFilterInWatchlistEffective" class="space-y-2">
            <p class="text-xs text-muted">Quick filters</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-if="showQuickFilterHasUpcomingEffective"
                type="button"
                class="chip-toggle"
                :data-on="staged.hasUpcoming ? 'true' : 'false'"
                @click="staged.hasUpcoming = !staged.hasUpcoming"
              >
                Has upcoming
              </button>
              <button
                v-if="showQuickFilterNewOnlyEffective"
                type="button"
                class="chip-toggle"
                :data-on="staged.newOnly ? 'true' : 'false'"
                @click="staged.newOnly = !staged.newOnly"
              >
                New episodes
              </button>
              <button
                v-if="showQuickFilterMissingRatingEffective"
                type="button"
                class="chip-toggle"
                :data-on="staged.missingRating ? 'true' : 'false'"
                @click="staged.missingRating = !staged.missingRating"
              >
                Missing rating
              </button>
              <button
                v-if="showQuickFilterInWatchlistEffective"
                type="button"
                class="chip-toggle"
                :data-on="staged.inWatchlist ? 'true' : 'false'"
                @click="staged.inWatchlist = !staged.inWatchlist"
              >
                In watchlist
              </button>
            </div>
          </div>

          <div v-if="props.showStatusFilter" class="space-y-2">
            <p class="text-xs text-muted">User status</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="statusOption in resolvedStatusChipOptions"
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

          <div v-if="props.showProviderStatusFilter" class="space-y-2">
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

          <div v-if="props.showGenreFilter" class="space-y-2">
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

          <div v-if="showMediaTypeControl" class="space-y-2">
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

      <details v-if="showSort" ref="sortMenuRef" class="relative control-menu">
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
  mediaType: { type: String, default: 'all' },
  showStatusFilter: { type: Boolean, default: false },
  showProviderStatusFilter: { type: Boolean, default: false },
  showGenreFilter: { type: Boolean, default: true },
  showQuickFilterHasUpcoming: { type: Boolean, default: false },
  showQuickFilterNewOnly: { type: Boolean, default: false },
  showQuickFilterMissingRating: { type: Boolean, default: false },
  showQuickFilterInWatchlist: { type: Boolean, default: false },
  showSearch: { type: Boolean, default: true },
  showSort: { type: Boolean, default: true },
  showDirection: { type: Boolean, default: true },
  defaultSortKey: { type: String, default: 'added_at' },
  searchPlaceholder: { type: String, default: 'Search by title' },
  advancedLabel: { type: String, default: 'Advanced Filters' },
  applyMediaTypeExclusiveSorts: { type: Boolean, default: true },
  showOrderSort: { type: Boolean, default: false },
  providerStatusOptions: { type: Array, default: () => [] },
  genreOptions: { type: Array, default: () => [] },
  page: { type: Number, default: 1 },
  syncUrl: { type: Boolean, default: true },
})

const emit = defineEmits(['change'])

const route = useRoute()
const router = useRouter()
const rootRef = ref(null)
const sortMenuRef = ref(null)
const advancedOpen = ref(false)
const directionOverridden = ref(false)
const draftSearch = ref('')
const fetchedGenres = ref([])

const tvStatusChipOptions = [
  { label: 'Plan to watch', value: 'plan_to_watch' },
  { label: 'Watching', value: 'watching' },
  { label: 'Completed', value: 'watched' },
  { label: 'Dropped', value: 'dropped' },
]

const movieStatusChipOptions = [
  { label: 'Plan to watch', value: 'plan_to_watch' },
  { label: 'Watched', value: 'watched' },
  { label: 'Dropped', value: 'dropped' },
]

const sortLabelsByKey = {
  added_at: 'Date added',
  custom_order: 'Custom order',
  title: 'Title',
  rating: 'Rating',
  vote_count: 'Votes',
  runtime: 'Runtime',
  release_date: 'Release date',
  watched_date: 'Watched date',
  time_left: 'Time left',
  episodes_left: 'Episodes left',
  last_watched: 'Last watched',
  started_date: 'Started date',
  progress_percent: 'Progress',
  next_episode_date: 'Next episode date',
}

const baseDefaultDirections = {
  added_at: 'asc',
  custom_order: 'asc',
  title: 'asc',
  rating: 'desc',
  vote_count: 'desc',
  runtime: 'asc',
  release_date: 'desc',
  watched_date: 'desc',
  time_left: 'asc',
  episodes_left: 'asc',
  last_watched: 'desc',
  started_date: 'asc',
  progress_percent: 'desc',
  next_episode_date: 'desc',
}

const sortBaselineKeys = ['added_at', 'title', 'rating', 'vote_count', 'runtime', 'release_date']
const sortMovieBaselineKeys = ['title', 'rating', 'runtime', 'release_date']
const sortMovieExclusiveKeys = ['watched_date']
const sortTvExclusiveKeys = ['time_left', 'episodes_left', 'last_watched', 'started_date', 'progress_percent', 'next_episode_date']

const showMediaTypeControl = computed(() => props.mediaType === 'all')

const filters = reactive({
  search: '',
  sort: props.defaultSortKey,
  direction: getDefaultDirection(props.defaultSortKey),
  mediaType: props.mediaType,
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
  inWatchlist: false,
})

const staged = reactive({
  mediaType: props.mediaType,
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
  inWatchlist: false,
})

const effectiveMediaType = computed(() => {
  if (showMediaTypeControl.value) {
    return filters.mediaType || props.mediaType || 'all'
  }
  return props.mediaType || 'all'
})

const showQuickFilterHasUpcomingEffective = computed(() => props.showQuickFilterHasUpcoming)
const showQuickFilterNewOnlyEffective = computed(() => props.showQuickFilterNewOnly)
const showQuickFilterMissingRatingEffective = computed(() => props.showQuickFilterMissingRating)
const showQuickFilterInWatchlistEffective = computed(() => props.showQuickFilterInWatchlist)
const usesStatusWorkflowSortProfile = computed(() => {
  return (
    props.showStatusFilter
    && props.showProviderStatusFilter
    && props.showQuickFilterHasUpcoming
    && props.showQuickFilterNewOnly
  )
})

const resolvedGenreOptions = computed(() => {
  const fromProps = props.genreOptions || []
  const fromApi = fetchedGenres.value || []
  return [...new Set([...fromProps, ...fromApi])].sort((a, b) => a.localeCompare(b))
})

const resolvedStatusChipOptions = computed(() => (
  effectiveMediaType.value === 'movie' ? movieStatusChipOptions : tvStatusChipOptions
))

const resolvedSortOptions = computed(() => {
  let baseline
  if (effectiveMediaType.value === 'movie') {
    baseline = sortMovieBaselineKeys
  } else {
    baseline = usesStatusWorkflowSortProfile.value ? ['title', 'release_date'] : sortBaselineKeys
  }
  const keys = [...baseline]
  if (props.showOrderSort) {
    keys.unshift('custom_order')
  }
  if (props.applyMediaTypeExclusiveSorts) {
    if (effectiveMediaType.value === 'movie') {
      keys.push(...sortMovieExclusiveKeys)
    } else if (effectiveMediaType.value === 'tv') {
      keys.push(...sortTvExclusiveKeys)
    }
  }
  return dedupeSortKeys(keys).map((key) => ({
    label: sortLabelsByKey[key] || key,
    value: key,
  }))
})

const resolvedDefaultSort = computed(() => {
  const keys = resolvedSortOptions.value.map((option) => option.value)
  if (keys.includes(props.defaultSortKey)) {
    return props.defaultSortKey
  }
  if (keys.includes('title')) {
    return 'title'
  }
  return keys[0] || 'added_at'
})

const mediaTypeAdvancedOptions = [
  { label: 'Movies', value: 'movie' },
  { label: 'Shows', value: 'tv' },
]

const hasAdvancedFilters = computed(() => {
  return (
    showMediaTypeControl.value
    || props.showStatusFilter
    || props.showProviderStatusFilter
    || props.showGenreFilter
    || showQuickFilterHasUpcomingEffective.value
    || showQuickFilterNewOnlyEffective.value
    || showQuickFilterMissingRatingEffective.value
    || showQuickFilterInWatchlistEffective.value
  )
})

const currentSortLabel = computed(() => {
  return resolvedSortOptions.value.find((option) => option.value === filters.sort)?.label || 'Sort'
})

const activeAdvancedCount = computed(() => {
  let total = 0
  if (showMediaTypeControl.value && filters.mediaType !== 'all') total += 1
  if (props.showStatusFilter) total += filters.statuses.length
  if (props.showProviderStatusFilter) total += filters.providerStatuses.length
  if (props.showGenreFilter) total += filters.genres.length
  if (showQuickFilterHasUpcomingEffective.value && filters.hasUpcoming) total += 1
  if (showQuickFilterNewOnlyEffective.value && filters.newOnly) total += 1
  if (showQuickFilterMissingRatingEffective.value && filters.missingRating) total += 1
  if (showQuickFilterInWatchlistEffective.value && filters.inWatchlist) total += 1
  return total
})

onClickOutside(rootRef, () => {
  if (!advancedOpen.value) return
  advancedOpen.value = false
  syncStagedFromApplied()
})

onClickOutside(sortMenuRef, () => {
  if (!sortMenuRef.value?.open) return
  sortMenuRef.value.open = false
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
  { deep: true }
)

function getDefaultDirection(sortKey) {
  return baseDefaultDirections[sortKey] || 'asc'
}

function serializeFilters(value) {
  return JSON.stringify({
    search: value.search || '',
    sort: value.sort || resolvedDefaultSort.value,
    direction: value.direction || getDefaultDirection(value.sort || resolvedDefaultSort.value),
    mediaType: value.mediaType || props.mediaType || 'all',
    statuses: [...(value.statuses || [])].sort(),
    providerStatuses: [...(value.providerStatuses || [])].sort(),
    genres: [...(value.genres || [])].sort(),
    hasUpcoming: Boolean(value.hasUpcoming),
    newOnly: Boolean(value.newOnly),
    missingRating: Boolean(value.missingRating),
    inWatchlist: Boolean(value.inWatchlist),
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
  filters.inWatchlist = next.inWatchlist
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
    sort: typeof query.sort === 'string' ? query.sort : resolvedDefaultSort.value,
    direction: '',
    directionOverridden: false,
    mediaType: props.mediaType || 'all',
    statuses: parseArray(query.status),
    providerStatuses: parseArray(query.provider_status),
    genres: parseArray(query.genres),
    hasUpcoming: query.has_upcoming === '1',
    newOnly: query.is_new === '1',
    missingRating: query.missing_rating === '1',
    inWatchlist: query.in_watchlist === '1',
  }

  if (showMediaTypeControl.value) {
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
    next.sort = resolvedDefaultSort.value
    if (!next.directionOverridden) {
      next.direction = getDefaultDirection(next.sort)
    }
  }

  if (!props.showQuickFilterHasUpcoming) next.hasUpcoming = false
  if (!props.showQuickFilterNewOnly) next.newOnly = false
  if (!props.showQuickFilterMissingRating) next.missingRating = false
  if (!showQuickFilterInWatchlistEffective.value) next.inWatchlist = false
  if (!props.showStatusFilter) next.statuses = []
  if (!props.showProviderStatusFilter) next.providerStatuses = []
  if (!props.showGenreFilter) next.genres = []

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
  staged.inWatchlist = filters.inWatchlist
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
    inWatchlist: filters.inWatchlist,
  }
  emit('change', { source, filters: payload })
}

// Synchronous initial hydration — parent receives correct filters before its first load.
// This serializes hydration before any view's immediate watcher can fetch with defaults.
const _initialFilters = parseFromQuery(route.query)
applyFiltersState(_initialFilters)
emitChange('hydrate')

const filterQueryKeys = ['search', 'sort', 'direction', 'media_type', 'status', 'provider_status', 'has_upcoming', 'is_new', 'missing_rating', 'in_watchlist', 'genres', 'page']

function resolvePageValue(value) {
  const page = Number.parseInt(String(value ?? 1), 10)
  return Number.isInteger(page) && page > 0 ? page : 1
}

function syncUrl(options = {}) {
  if (!props.syncUrl) return

  const { resetPage = false } = options
  const nextPage = resetPage ? 1 : resolvePageValue(props.page)

  // Owned keys are composed purely from component state (never from the live
  // route query) so concurrent writes in one tick can never clobber each other.
  // Foreign query params are preserved as-is.
  const nextQuery = { ...route.query }
  for (const key of filterQueryKeys) {
    delete nextQuery[key]
  }
  if (nextPage > 1) {
    nextQuery.page = String(nextPage)
  }

  if (props.showSearch && filters.search) nextQuery.search = filters.search
  if (props.showSort && filters.sort !== resolvedDefaultSort.value) nextQuery.sort = filters.sort
  if (props.showDirection && (directionOverridden.value || filters.direction !== getDefaultDirection(filters.sort))) {
    nextQuery.direction = filters.direction
  }
  if (showMediaTypeControl.value && filters.mediaType !== 'all') nextQuery.media_type = filters.mediaType

  if (props.showStatusFilter && filters.statuses.length) nextQuery.status = [...filters.statuses]
  if (props.showProviderStatusFilter && filters.providerStatuses.length) nextQuery.provider_status = [...filters.providerStatuses]
  if (props.showGenreFilter && filters.genres.length) nextQuery.genres = [...filters.genres]
  if (showQuickFilterHasUpcomingEffective.value && filters.hasUpcoming) nextQuery.has_upcoming = '1'
  if (showQuickFilterNewOnlyEffective.value && filters.newOnly) nextQuery.is_new = '1'
  if (showQuickFilterMissingRatingEffective.value && filters.missingRating) nextQuery.missing_rating = '1'
  if (showQuickFilterInWatchlistEffective.value && filters.inWatchlist) nextQuery.in_watchlist = '1'

  if (JSON.stringify(nextQuery) !== JSON.stringify(route.query)) {
    router.replace({ query: nextQuery })
  }
}

function commitInteraction() {
  syncUrl({ resetPage: true })
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
  filters.mediaType = showMediaTypeControl.value ? staged.mediaType : (props.mediaType || 'all')
  filters.statuses = props.showStatusFilter ? [...staged.statuses] : []
  filters.providerStatuses = props.showProviderStatusFilter ? [...staged.providerStatuses] : []
  filters.genres = props.showGenreFilter ? [...staged.genres] : []
  filters.hasUpcoming = showQuickFilterHasUpcomingEffective.value ? staged.hasUpcoming : false
  filters.newOnly = showQuickFilterNewOnlyEffective.value ? staged.newOnly : false
  filters.missingRating = showQuickFilterMissingRatingEffective.value ? staged.missingRating : false
  filters.inWatchlist = showQuickFilterInWatchlistEffective.value ? staged.inWatchlist : false
  advancedOpen.value = false
  commitInteraction()
}

function clearAdvanced() {
  staged.mediaType = showMediaTypeControl.value ? 'all' : (props.mediaType || 'all')
  staged.statuses = []
  staged.providerStatuses = []
  staged.genres = []
  staged.hasUpcoming = false
  staged.newOnly = false
  staged.missingRating = false
  staged.inWatchlist = false
  applyAdvanced()
}

function clearAll() {
  draftSearch.value = ''
  filters.search = ''
  filters.sort = resolvedDefaultSort.value
  filters.direction = getDefaultDirection(filters.sort)
  directionOverridden.value = false
  filters.mediaType = showMediaTypeControl.value ? 'all' : (props.mediaType || 'all')
  filters.statuses = []
  filters.providerStatuses = []
  filters.genres = []
  filters.hasUpcoming = false
  filters.newOnly = false
  filters.missingRating = false
  filters.inWatchlist = false
  advancedOpen.value = false
  syncStagedFromApplied()
  commitInteraction()
}

defineExpose({ clearAll })

function applySearch() {
  filters.search = draftSearch.value.trim()
  commitInteraction()
}

function setSort(nextSort) {
  filters.sort = nextSort
  if (!directionOverridden.value) {
    filters.direction = getDefaultDirection(nextSort)
  }
  if (sortMenuRef.value?.open) {
    sortMenuRef.value.open = false
  }
  commitInteraction()
}

watch(
  [resolvedSortOptions, resolvedDefaultSort],
  () => {
    if (resolvedSortOptions.value.some((option) => option.value === filters.sort)) {
      return
    }
    filters.sort = resolvedDefaultSort.value
    if (!directionOverridden.value) {
      filters.direction = getDefaultDirection(filters.sort)
    }
    commitInteraction()
  },
  { deep: true }
)

watch(
  effectiveMediaType,
  () => {
    if (resolvedSortOptions.value.some((option) => option.value === filters.sort)) return
    filters.sort = resolvedDefaultSort.value
    if (!directionOverridden.value) {
      filters.direction = getDefaultDirection(filters.sort)
    }
  }
)

watch(
  () => props.mediaType,
  () => {
    if (showMediaTypeControl.value) {
      return
    }
    filters.mediaType = props.mediaType || 'all'
    staged.mediaType = props.mediaType || 'all'
  }
)

watch(
  () => props.page,
  () => {
    if (!props.syncUrl) return
    syncUrl()
  }
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

function dedupeSortKeys(values) {
  const seen = new Set()
  const keys = []
  for (const value of values || []) {
    const key = String(value || '').trim()
    if (!key || seen.has(key)) continue
    seen.add(key)
    keys.push(key)
  }
  return keys
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
