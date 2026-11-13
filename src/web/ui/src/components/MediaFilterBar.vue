<template>
  <div class="card filter-controls mb-5 p-3 md:p-4 space-y-3" ref="rootRef">
    <div class="flex flex-col lg:flex-row gap-2">
      <div class="relative">
        <button type="button" class="control-trigger" @click="toggleAdvanced">
          <span class="inline-flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18l-7 8v6l-4 2v-8L3 4z"/>
            </svg>
            <span>{{ advancedLabelText }}</span>
            <span v-if="activeAdvancedCount" class="control-count">{{ activeAdvancedCount }}</span>
          </span>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>

        <div v-if="advancedOpen" class="control-panel left-0 w-[20rem] max-w-[85vw] p-3 space-y-3">
          <div v-if="visibleQuickFilters.length" class="space-y-2">
            <p class="text-xs text-muted">{{ t('filter_bar_quick_filters') }}</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="option in visibleQuickFilters"
                :key="option.key"
                type="button"
                class="chip-toggle"
                :data-on="staged[option.key] ? 'true' : 'false'"
                @click="staged[option.key] = !staged[option.key]"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <div v-if="panelFilters.has('statuses')" class="space-y-2">
            <p class="text-xs text-muted">{{ t('filter_bar_user_status') }}</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="statusOption in panelStatusChipOptions"
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

          <div v-if="panelFilters.has('providerStatuses') && props.providerStatusOptions.length" class="space-y-2">
            <p class="text-xs text-muted">{{ t('filter_bar_show_status') }}</p>
            <div class="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
              <button
                v-for="providerStatus in props.providerStatusOptions"
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

          <div class="space-y-2">
            <p class="text-xs text-muted">{{ t('filter_bar_genres') }}</p>
            <div class="flex max-h-32 flex-wrap gap-2 overflow-y-auto">
              <button
                v-for="genre in fetchedGenres"
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
            <p class="text-xs text-muted">{{ t('filter_bar_media_type') }}</p>
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
            <button type="button" class="btn-ghost text-xs px-3 py-1.5" @click="clearAdvanced">{{ t('filter_bar_clear_all') }}</button>
            <button type="button" class="btn-primary text-xs px-3 py-1.5" @click="applyAdvanced">{{ t('filter_bar_apply') }}</button>
          </div>
        </div>
      </div>

      <div class="relative flex-1">
        <input
          v-model="draftSearch"
          type="text"
          class="input text-sm pl-10"
          :placeholder="searchPlaceholderText"
          @keydown.enter="applySearch"
        >
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>

      <details ref="sortMenuRef" class="relative control-menu">
        <summary class="control-trigger">
          <span class="inline-flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4h18M7 12h10M10 20h4"/>
            </svg>
            <span>{{ t('filter_bar_sorted_by') }}</span>
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
        type="button"
        class="control-trigger direction-trigger"
        :title="filters.direction === 'asc' ? t('filter_bar_ascending') : t('filter_bar_descending')"
        :aria-label="filters.direction === 'asc' ? t('filter_bar_sorting_ascending') : t('filter_bar_sorting_descending')"
        @click="setDirection(filters.direction === 'asc' ? 'desc' : 'asc')"
      >
        <span class="inline-flex items-center gap-1.5">
          <ArrowDownNarrowWide v-if="filters.direction === 'asc'" class="w-4 h-4" :stroke-width="2" aria-hidden="true" />
          <ArrowDownWideNarrow v-else class="w-4 h-4" :stroke-width="2" aria-hidden="true" />
          <span>{{ filters.direction === 'asc' ? t('filter_bar_direction_asc') : t('filter_bar_direction_desc') }}</span>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { LocationQuery, LocationQueryRaw, LocationQueryValue } from 'vue-router'
import { onClickOutside } from '@vueuse/core'
import { ArrowDownNarrowWide, ArrowDownWideNarrow } from '@lucide/vue'
import { mediaAPI } from '@/api'
import { useI18n } from '@/i18n'
import type { MessageKey } from '@/i18n'

type FilterBarKind = 'watchlist' | 'list' | 'library'
type MediaTypeFilter = 'all' | 'movie' | 'tv'
type SortDirection = 'asc' | 'desc'
type FilterArrayKey = 'statuses' | 'providerStatuses' | 'genres'
type FilterFlagKey = 'missingRating' | 'inWatchlist' | 'hasUpcoming' | 'newOnly' | 'hasNextEpisode'
type ConditionalFilterKey = 'statuses' | 'providerStatuses' | FilterFlagKey
type FilterChangeSource = 'hydrate' | 'interaction'

interface MediaFilterBarProps {
  kind: FilterBarKind
  mediaType?: MediaTypeFilter
  searchPlaceholder?: string
  advancedLabel?: string
  providerStatusOptions?: string[]
  page?: number
  syncUrl?: boolean
}

interface FilterState {
  search: string
  sort: string
  direction: SortDirection
  mediaType: MediaTypeFilter
  statuses: string[]
  providerStatuses: string[]
  genres: string[]
  hasUpcoming: boolean
  newOnly: boolean
  missingRating: boolean
  hasNextEpisode: boolean
  inWatchlist: boolean
}

interface ParsedFilterState extends FilterState {
  directionOverridden: boolean
}

interface StagedFilterState extends Omit<FilterState, 'search' | 'sort' | 'direction'> {}

interface SortOption {
  label: string
  value: string
}

interface SyncUrlOptions {
  resetPage?: boolean
}

interface ByMediaType<T> {
  base: T[]
  movie: T[]
  tv: T[]
}

interface KindProfile {
  sorts: ByMediaType<string>
  filters: ByMediaType<ConditionalFilterKey>
  defaultSort: Record<MediaTypeFilter, string>
  impliedStatuses?: string[]
}

interface Availability {
  sorts: string[]
  filters: Set<ConditionalFilterKey>
  statuses: string[]
}

const props = withDefaults(defineProps<MediaFilterBarProps>(), {
  mediaType: 'all',
  providerStatusOptions: () => [],
  page: 1,
  syncUrl: true,
})

const emit = defineEmits<{
  change: [payload: { source: FilterChangeSource; filters: FilterState }]
}>()

const { t } = useI18n()
const searchPlaceholderText = computed(() => props.searchPlaceholder ?? t('filter_bar_search_placeholder'))
const advancedLabelText = computed(() => props.advancedLabel ?? t('filter_bar_advanced'))
const route = useRoute()
const router = useRouter()
const rootRef = ref<HTMLElement | null>(null)
const sortMenuRef = ref<HTMLDetailsElement | null>(null)
const advancedOpen = ref(false)
const directionOverridden = ref(false)
const draftSearch = ref('')
const fetchedGenres = ref<string[]>([])

const tvStatusChipKeys: { key: MessageKey; value: string }[] = [
  { key: 'status_plan_to_watch', value: 'plan_to_watch' },
  { key: 'watch_action_watching', value: 'watching' },
  { key: 'watch_action_watched', value: 'watched' },
  { key: 'watch_action_dropped', value: 'dropped' },
]

const movieStatusChipKeys: { key: MessageKey; value: string }[] = [
  { key: 'status_plan_to_watch', value: 'plan_to_watch' },
  { key: 'watch_action_watched', value: 'watched' },
  { key: 'watch_action_dropped', value: 'dropped' },
]

const quickFilterOptions: { key: FilterFlagKey; label: MessageKey }[] = [
  { key: 'hasUpcoming', label: 'filter_bar_quick_has_upcoming' },
  { key: 'newOnly', label: 'filter_bar_quick_new_episodes' },
  { key: 'missingRating', label: 'filter_bar_quick_missing_rating' },
  { key: 'hasNextEpisode', label: 'filter_bar_quick_has_next_episode' },
  { key: 'inWatchlist', label: 'filter_bar_quick_in_watchlist' },
]

const sortLabelKeys: Record<string, MessageKey> = {
  added_at: 'filter_bar_sort_added_at',
  custom_order: 'filter_bar_sort_custom_order',
  title: 'filter_bar_sort_title',
  provider_rating: 'filter_bar_sort_provider_rating',
  user_rating: 'filter_bar_sort_user_rating',
  vote_count: 'filter_bar_sort_vote_count',
  runtime: 'movie_runtime',
  episode_runtime: 'filter_bar_sort_episode_runtime',
  release_date: 'watch_option_release',
  watched_date: 'filter_bar_sort_watched_date',
  time_left: 'filter_bar_sort_time_left',
  episodes_left: 'filter_bar_sort_episodes_left',
  last_watched: 'progress_row_last_watched',
  started_date: 'filter_bar_sort_started_date',
  progress_percent: 'filter_bar_sort_progress_percent',
  next_episode_date: 'filter_bar_sort_next_episode_date',
}

const baseDefaultDirections: Record<string, SortDirection> = {
  added_at: 'asc',
  custom_order: 'asc',
  title: 'asc',
  provider_rating: 'desc',
  user_rating: 'desc',
  vote_count: 'desc',
  runtime: 'asc',
  episode_runtime: 'asc',
  release_date: 'desc',
  watched_date: 'desc',
  time_left: 'asc',
  episodes_left: 'asc',
  last_watched: 'desc',
  started_date: 'asc',
  progress_percent: 'desc',
  next_episode_date: 'desc',
}

const tvProgressSorts = ['last_watched', 'started_date', 'progress_percent', 'next_episode_date', 'episodes_left', 'time_left']

const profiles: Record<FilterBarKind, KindProfile> = {
  watchlist: {
    sorts: {
      base: ['added_at', 'title', 'vote_count', 'runtime', 'release_date', 'provider_rating'],
      movie: [],
      tv: ['episode_runtime'],
    },
    filters: { base: [], movie: [], tv: ['providerStatuses'] },
    defaultSort: { all: 'added_at', movie: 'added_at', tv: 'added_at' },
    impliedStatuses: ['plan_to_watch'],
  },
  list: {
    sorts: {
      base: ['custom_order', 'added_at', 'title', 'vote_count', 'runtime', 'release_date', 'provider_rating', 'user_rating'],
      movie: ['watched_date'],
      tv: ['episode_runtime', ...tvProgressSorts],
    },
    filters: { base: ['statuses', 'missingRating', 'inWatchlist'], movie: [], tv: ['providerStatuses'] },
    defaultSort: { all: 'custom_order', movie: 'custom_order', tv: 'custom_order' },
  },
  library: {
    sorts: {
      base: ['title', 'vote_count', 'runtime', 'release_date', 'provider_rating', 'user_rating'],
      movie: ['watched_date'],
      tv: ['episode_runtime', ...tvProgressSorts],
    },
    filters: {
      base: ['statuses', 'missingRating'],
      movie: [],
      tv: ['providerStatuses', 'hasUpcoming', 'newOnly', 'hasNextEpisode'],
    },
    defaultSort: { all: 'title', movie: 'watched_date', tv: 'last_watched' },
  },
}

// Sorts and filters that only make sense once an item has been started or finished.
const startedOnlySorts = new Set(['watched_date', 'started_date', 'last_watched', 'progress_percent', 'time_left', 'episodes_left', 'next_episode_date'])
const startedOnlyFilters = new Set<ConditionalFilterKey>(['missingRating'])

const arrayFilterKeys: FilterArrayKey[] = ['statuses', 'providerStatuses', 'genres']
const flagFilterKeys: FilterFlagKey[] = ['missingRating', 'inWatchlist', 'hasUpcoming', 'newOnly', 'hasNextEpisode']
const flagQueryKeys: Record<FilterFlagKey, string> = {
  hasUpcoming: 'has_upcoming',
  newOnly: 'is_new',
  missingRating: 'missing_rating',
  hasNextEpisode: 'has_next_episode',
  inWatchlist: 'in_watchlist',
}

const showMediaTypeControl = computed(() => props.mediaType === 'all')

const filters = reactive<FilterState>({
  search: '',
  sort: profiles[props.kind].defaultSort[props.mediaType],
  direction: getDefaultDirection(profiles[props.kind].defaultSort[props.mediaType]),
  mediaType: props.mediaType,
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
  hasNextEpisode: false,
  inWatchlist: false,
})

const staged = reactive<StagedFilterState>({
  mediaType: props.mediaType,
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
  hasNextEpisode: false,
  inWatchlist: false,
})

const effectiveMediaType = computed(() => {
  if (showMediaTypeControl.value) {
    return filters.mediaType || props.mediaType || 'all'
  }
  return props.mediaType || 'all'
})

const availability = computed(() => resolveAvailability(effectiveMediaType.value, filters.statuses))
const panelAvailability = computed(() => (
  advancedOpen.value ? resolveAvailability(staged.mediaType, staged.statuses) : availability.value
))
const panelFilters = computed(() => panelAvailability.value.filters)

const panelStatusChipOptions = computed<SortOption[]>(() => statusChipOptionsFor(staged.mediaType))

const visibleQuickFilters = computed(() => quickFilterOptions
  .filter((option) => panelFilters.value.has(option.key))
  .map((option) => ({ key: option.key, label: t(option.label) })))

const resolvedSortOptions = computed<SortOption[]>(() => (
  dedupeSortKeys(availability.value.sorts).map((key) => {
    const labelKey = sortLabelKeys[key]
    return { label: labelKey ? t(labelKey) : key, value: key }
  })
))

const resolvedDefaultSort = computed<string>(() => pickDefaultSort(effectiveMediaType.value, availability.value.sorts))

const mediaTypeAdvancedOptions = computed<{ label: string; value: Exclude<MediaTypeFilter, 'all'> }[]>(() => [
  { label: t('history_filter_movies'), value: 'movie' },
  { label: t('filter_bar_media_shows'), value: 'tv' },
])

const currentSortLabel = computed(() => {
  return resolvedSortOptions.value.find((option) => option.value === filters.sort)?.label || t('filter_bar_sort')
})

const activeAdvancedCount = computed(() => {
  let total = 0
  if (showMediaTypeControl.value && filters.mediaType !== 'all') total += 1
  for (const key of arrayFilterKeys) total += filters[key].length
  for (const key of flagFilterKeys) if (filters[key]) total += 1
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
      ? data.map((genre) => genre.name).filter((name): name is string => Boolean(name))
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

function getDefaultDirection(sortKey: string): SortDirection {
  return baseDefaultDirections[sortKey] || 'asc'
}

function statusChipOptionsFor(mediaType: MediaTypeFilter): SortOption[] {
  const chips = mediaType === 'movie' ? movieStatusChipKeys : tvStatusChipKeys
  return chips.map((chip) => ({ label: t(chip.key), value: chip.value }))
}

function resolveAvailability(mediaType: MediaTypeFilter, selectedStatuses: string[]): Availability {
  const profile = profiles[props.kind]
  const pick = <T,>(group: ByMediaType<T>): T[] => [...group.base, ...(mediaType === 'all' ? [] : group[mediaType])]

  const filterKeys = pick(profile.filters)
  const validStatuses = new Set(statusChipOptionsFor(mediaType).map((option) => option.value))
  const statuses = filterKeys.includes('statuses')
    ? selectedStatuses.filter((status) => validStatuses.has(status))
    : []
  const effectiveStatuses = profile.impliedStatuses ?? statuses
  const notStarted = effectiveStatuses.length > 0 && effectiveStatuses.every((status) => status === 'plan_to_watch')

  return {
    sorts: pick(profile.sorts).filter((key) => !(notStarted && startedOnlySorts.has(key))),
    filters: new Set(filterKeys.filter((key) => !(notStarted && startedOnlyFilters.has(key)))),
    statuses,
  }
}

function pickDefaultSort(mediaType: MediaTypeFilter, sorts: string[]): string {
  const preferred = profiles[props.kind].defaultSort[mediaType]
  if (sorts.includes(preferred)) return preferred
  if (sorts.includes('title')) return 'title'
  return sorts[0] || 'added_at'
}

function normalizeAdvancedState(state: StagedFilterState): Availability {
  const result = resolveAvailability(state.mediaType, state.statuses)
  state.statuses = result.statuses
  if (!result.filters.has('providerStatuses')) state.providerStatuses = []
  for (const key of flagFilterKeys) {
    if (!result.filters.has(key)) state[key] = false
  }
  return result
}

function reconcileSort(): boolean {
  if (availability.value.sorts.includes(filters.sort)) return false
  filters.sort = resolvedDefaultSort.value
  if (!directionOverridden.value) {
    filters.direction = getDefaultDirection(filters.sort)
  }
  return true
}

function serializeFilters(value: FilterState): string {
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
    hasNextEpisode: Boolean(value.hasNextEpisode),
    inWatchlist: Boolean(value.inWatchlist),
  })
}

function copyAdvancedState(source: StagedFilterState, target: StagedFilterState): void {
  target.mediaType = source.mediaType
  for (const key of arrayFilterKeys) target[key] = [...source[key]]
  for (const key of flagFilterKeys) target[key] = source[key]
}

function applyFiltersState(next: ParsedFilterState): void {
  filters.search = next.search
  filters.sort = next.sort
  filters.direction = next.direction
  copyAdvancedState(next, filters)
  draftSearch.value = next.search
  directionOverridden.value = next.directionOverridden
  syncStagedFromApplied()
}

function parseArray(queryValue: LocationQueryValue | LocationQueryValue[] | undefined): string[] {
  if (Array.isArray(queryValue)) {
    return queryValue.map((entry) => String(entry)).filter(Boolean)
  }
  if (typeof queryValue === 'string' && queryValue) {
    return [queryValue]
  }
  return []
}

function parseFromQuery(query: LocationQuery): ParsedFilterState {
  let mediaType: MediaTypeFilter = props.mediaType
  if (showMediaTypeControl.value) {
    mediaType = query.media_type === 'movie' || query.media_type === 'tv' ? query.media_type : 'all'
  }

  const next: ParsedFilterState = {
    search: typeof query.search === 'string' ? query.search : '',
    sort: typeof query.sort === 'string' ? query.sort : '',
    direction: 'asc',
    directionOverridden: query.direction === 'asc' || query.direction === 'desc',
    mediaType,
    statuses: parseArray(query.status),
    providerStatuses: parseArray(query.provider_status),
    genres: parseArray(query.genres),
    hasUpcoming: false,
    newOnly: false,
    missingRating: false,
    hasNextEpisode: false,
    inWatchlist: false,
  }
  for (const key of flagFilterKeys) next[key] = query[flagQueryKeys[key]] === '1'

  const { sorts } = normalizeAdvancedState(next)
  if (!sorts.includes(next.sort)) next.sort = pickDefaultSort(mediaType, sorts)
  next.direction = query.direction === 'asc' || query.direction === 'desc'
    ? query.direction
    : getDefaultDirection(next.sort)

  return next
}

function syncStagedFromApplied(): void {
  copyAdvancedState(filters, staged)
}

function emitChange(source: FilterChangeSource): void {
  const payload: FilterState = {
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
    hasNextEpisode: filters.hasNextEpisode,
    inWatchlist: filters.inWatchlist,
  }
  emit('change', { source, filters: payload })
}

// Synchronous initial hydration — parent receives correct filters before its first load.
// This serializes hydration before any view's immediate watcher can fetch with defaults.
applyFiltersState(parseFromQuery(route.query))
emitChange('hydrate')

const filterQueryKeys = ['search', 'sort', 'direction', 'media_type', 'status', 'provider_status', ...Object.values(flagQueryKeys), 'genres', 'page'] as const

function resolvePageValue(value: unknown): number {
  const page = Number.parseInt(String(value ?? 1), 10)
  return Number.isInteger(page) && page > 0 ? page : 1
}

function syncUrl(options: SyncUrlOptions = {}): void {
  if (!props.syncUrl) return

  const { resetPage = false } = options
  const nextPage = resetPage ? 1 : resolvePageValue(props.page)

  // Owned keys are composed purely from component state (never from the live
  // route query) so concurrent writes in one tick can never clobber each other.
  // Foreign query params are preserved as-is.
  const nextQuery: LocationQueryRaw = { ...route.query }
  for (const key of filterQueryKeys) {
    delete nextQuery[key]
  }
  if (nextPage > 1) {
    nextQuery.page = String(nextPage)
  }

  if (filters.search) nextQuery.search = filters.search
  if (filters.sort !== resolvedDefaultSort.value) nextQuery.sort = filters.sort
  if (directionOverridden.value || filters.direction !== getDefaultDirection(filters.sort)) {
    nextQuery.direction = filters.direction
  }
  if (showMediaTypeControl.value && filters.mediaType !== 'all') nextQuery.media_type = filters.mediaType

  if (filters.statuses.length) nextQuery.status = [...filters.statuses]
  if (filters.providerStatuses.length) nextQuery.provider_status = [...filters.providerStatuses]
  if (filters.genres.length) nextQuery.genres = [...filters.genres]
  for (const key of flagFilterKeys) {
    if (filters[key]) nextQuery[flagQueryKeys[key]] = '1'
  }

  if (JSON.stringify(nextQuery) !== JSON.stringify(route.query)) {
    router.push({ query: nextQuery })
  }
}

function commitInteraction(): void {
  syncUrl({ resetPage: true })
  emitChange('interaction')
}

function toggleStagedArrayValue(key: FilterArrayKey, value: string): void {
  if (staged[key].includes(value)) {
    staged[key] = staged[key].filter((entry) => entry !== value)
  } else {
    staged[key] = [...staged[key], value]
  }
}

function toggleAdvanced(): void {
  if (advancedOpen.value) {
    advancedOpen.value = false
    syncStagedFromApplied()
    return
  }
  syncStagedFromApplied()
  advancedOpen.value = true
}

function applyAdvanced(): void {
  copyAdvancedState(staged, filters)
  filters.mediaType = showMediaTypeControl.value ? staged.mediaType : (props.mediaType || 'all')
  normalizeAdvancedState(filters)
  reconcileSort()
  advancedOpen.value = false
  syncStagedFromApplied()
  commitInteraction()
}

function clearAdvanced(): void {
  staged.mediaType = showMediaTypeControl.value ? 'all' : (props.mediaType || 'all')
  for (const key of arrayFilterKeys) staged[key] = []
  for (const key of flagFilterKeys) staged[key] = false
  applyAdvanced()
}

function clearAll(): void {
  draftSearch.value = ''
  filters.search = ''
  directionOverridden.value = false
  filters.mediaType = showMediaTypeControl.value ? 'all' : (props.mediaType || 'all')
  for (const key of arrayFilterKeys) filters[key] = []
  for (const key of flagFilterKeys) filters[key] = false
  filters.sort = resolvedDefaultSort.value
  filters.direction = getDefaultDirection(filters.sort)
  advancedOpen.value = false
  syncStagedFromApplied()
  commitInteraction()
}

defineExpose({ clearAll })

function applySearch(): void {
  filters.search = draftSearch.value.trim()
  commitInteraction()
}

function setSort(nextSort: string): void {
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
  () => [props.kind, props.mediaType],
  () => {
    if (!showMediaTypeControl.value) {
      filters.mediaType = props.mediaType
      staged.mediaType = props.mediaType
    }
    normalizeAdvancedState(filters)
    if (reconcileSort()) commitInteraction()
  }
)

watch(
  () => props.page,
  () => {
    if (!props.syncUrl) return
    syncUrl()
  }
)

function setDirection(nextDirection: SortDirection): void {
  filters.direction = nextDirection
  directionOverridden.value = true
  commitInteraction()
}

function toggleStagedMediaType(nextType: Exclude<MediaTypeFilter, 'all'>): void {
  if (staged.mediaType === nextType) {
    staged.mediaType = 'all'
    return
  }
  staged.mediaType = nextType
}

function dedupeSortKeys(values: readonly string[]): string[] {
  const seen = new Set<string>()
  const keys: string[] = []
  for (const value of values) {
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
