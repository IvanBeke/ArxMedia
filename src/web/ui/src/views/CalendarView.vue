<template>
  <div class="w-full px-4 sm:px-6 lg:px-8 py-4 flex flex-col min-h-[calc(100dvh-3.5rem)]">
    <div class="max-w-7xl mx-auto w-full mb-4">
      <h1 class="font-display text-2xl text-primary font-semibold">Calendar</h1>
      <p class="text-muted text-sm">Watchlist movies and episodes from shows you are watching</p>
    </div>

    <section class="card p-4 flex-1 flex flex-col min-h-0">
      <div class="grid grid-cols-[auto_1fr_auto] items-center gap-3 mb-3">
        <div
          class="flex items-center rounded-lg border border-surface-300 bg-surface-100/60 p-1"
          role="group"
          aria-label="Calendar navigation"
        >
          <button
            class="p-1.5 rounded-md text-muted hover:text-primary hover:bg-surface-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            :aria-label="prevLabel"
            @click="goPrev"
          >
            <ChevronLeft class="w-4 h-4" />
          </button>
          <button
            class="px-3 py-1 mx-0.5 text-sm font-medium rounded-md text-brand-400 bg-brand-500/10 hover:bg-brand-500/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            @click="goToday"
          >
            Today
          </button>
          <button
            class="p-1.5 rounded-md text-muted hover:text-primary hover:bg-surface-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            :aria-label="nextLabel"
            @click="goNext"
          >
            <ChevronRight class="w-4 h-4" />
          </button>
        </div>
        <h2 class="section-title text-lg text-center truncate">{{ periodLabel }}</h2>
        <div
          class="hidden md:flex items-center rounded-lg border border-surface-300 bg-surface-100/60 p-0.5"
          role="group"
          aria-label="Calendar view mode"
        >
          <button
            v-for="mode in viewModes"
            :key="mode.value"
            class="px-3 py-1 text-sm rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            :class="effectiveViewMode === mode.value ? 'bg-brand-500 text-white shadow-sm' : 'text-muted hover:text-primary'"
            :aria-pressed="effectiveViewMode === mode.value"
            @click="setViewMode(mode.value)"
          >
            {{ mode.label }}
          </button>
        </div>
        <div class="md:hidden w-10" aria-hidden="true"></div>
      </div>

      <div v-if="effectiveViewMode !== 'day'" class="grid grid-cols-7 gap-2 mb-2">
        <div v-for="weekday in weekdays" :key="weekday" class="text-xs font-medium text-muted text-center py-2">
          {{ weekday }}
        </div>
      </div>

      <div v-if="loading" :class="effectiveViewMode === 'day' ? 'flex-1' : 'grid grid-cols-7 gap-2 flex-1'">
        <div v-for="n in skeletonCount" :key="n" class="min-h-28 skeleton rounded"></div>
      </div>

      <div v-else-if="effectiveViewMode === 'day'" class="flex-1 flex flex-col">
        <div
          v-if="dayItems.length === 0"
          class="flex-1 flex items-center justify-center rounded border border-surface-300 bg-surface-100/40 p-8 text-center"
        >
          <p class="text-sm text-muted">Nothing scheduled for this day.</p>
        </div>
        <div
          v-else
          class="rounded border border-surface-300 bg-surface-100/40 p-3 flex flex-col"
        >
          <div class="space-y-2">
            <RouterLink
              v-for="item in dayItems"
              :key="item.key"
              :to="item.to"
              class="block rounded px-3 py-2.5 bg-surface-200/60 text-primary hover:text-brand-400 transition-colors min-h-11"
              :title="item.label"
            >
              <span class="block text-base font-medium leading-snug">{{ item.label }}</span>
              <span class="block mt-0.5 text-xs leading-tight text-muted">
                <EpisodeCodePill
                  v-if="item.kind !== MEDIA_TYPE.MOVIE"
                  :season-number="item.seasonNumber"
                  :episode-number="item.episodeNumber"
                  variant="plain"
                  size="11px"
                />
                <span v-if="item.airTime" class="ml-1.5">{{ item.airTime }}</span>
                <template v-else>{{ item.sublabel }}</template>
              </span>
            </RouterLink>
          </div>
        </div>
      </div>

      <div v-else class="calendar-grid grid grid-cols-7 gap-2 flex-1">
        <div
          v-for="day in calendarDays"
          :key="day.iso"
          class="rounded border border-surface-300 p-2 flex flex-col min-w-0"
          :class="day.inCurrentMonth ? 'bg-surface-100/40' : 'bg-surface-200/30 opacity-60'"
        >
          <div class="text-xs mb-2 shrink-0" :class="day.isToday ? 'text-brand-400 font-semibold' : 'text-muted'">
            {{ day.date.day }}
          </div>
          <div class="space-y-1">
            <RouterLink
              v-for="item in day.items"
              :key="item.key"
              :to="item.to"
              class="block rounded px-1.5 py-1 bg-surface-200/60 text-primary hover:text-brand-400 transition-colors"
              :title="item.label"
            >
              <span class="block text-sm font-medium leading-snug truncate">{{ item.label }}</span>
              <span class="block mt-0.5 text-[11px] leading-tight text-muted">
                <EpisodeCodePill
                  v-if="item.kind !== MEDIA_TYPE.MOVIE"
                  :season-number="item.seasonNumber"
                  :episode-number="item.episodeNumber"
                  variant="plain"
                  size="11px"
                />
                <span v-if="item.airTime" class="ml-1.5">{{ item.airTime }}</span>
                <template v-else>{{ item.sublabel }}</template>
              </span>
            </RouterLink>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { useMediaQuery } from '@vueuse/core'
import { calendarAPI } from '@/api'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { isoDateKey, monthBounds, nowInstantIso, parsePlainDate, weekBounds } from '@/utils/temporal'
import type { CalendarItem } from '@/types/api'
import type { Temporal as TemporalPolyfill } from '@js-temporal/polyfill'

type ViewMode = 'day' | 'month' | 'week'
type CalendarDisplayItem = {
  key: string
  kind: CalendarItem['kind']
  label: string
  sublabel?: string
  seasonNumber?: number
  episodeNumber?: number
  airTime?: string
  to: string
}

function todayIso() {
  return isoDateKey(nowInstantIso())
}

const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const viewModes: { value: ViewMode; label: string }[] = [
  { value: 'day', label: 'Day' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
]
const loading = ref(true)
const desktopViewMode = ref<ViewMode>('month')
const anchorIso = ref(todayIso())
const items = ref<CalendarItem[]>([])

const isMobile = useMediaQuery('(max-width: 767px)')
const effectiveViewMode = computed<ViewMode>(() => (isMobile.value ? 'day' : desktopViewMode.value))

const skeletonCount = computed(() => {
  if (effectiveViewMode.value === 'day') return 1
  return effectiveViewMode.value === 'week' ? 7 : 42
})

const prevLabel = computed(() => {
  if (effectiveViewMode.value === 'day') return 'Previous day'
  return effectiveViewMode.value === 'week' ? 'Previous week' : 'Previous month'
})

const nextLabel = computed(() => {
  if (effectiveViewMode.value === 'day') return 'Next day'
  return effectiveViewMode.value === 'week' ? 'Next week' : 'Next month'
})

const periodLabel = computed(() => {
  if (effectiveViewMode.value === 'day') {
    return (
      parsePlainDate(anchorIso.value)?.toLocaleString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric'
      }) || ''
    )
  }
  if (effectiveViewMode.value === 'week') {
    const bounds = weekBounds(anchorIso.value)
    if (!bounds) {
      return ''
    }
    const { start, end } = bounds
    const startLabel = start.toLocaleString(undefined, { month: 'short', day: 'numeric' })
    if (start.year === end.year && start.month === end.month) {
      return `${startLabel} – ${end.day}, ${end.year}`
    }
    const endLabel = end.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      ...(start.year === end.year ? {} : { year: 'numeric' })
    })
    return `${startLabel} – ${endLabel}`
  }
  return parsePlainDate(anchorIso.value)?.toLocaleString(undefined, { month: 'long', year: 'numeric' }) || ''
})

const itemMap = computed(() => {
  const map = new Map<string, CalendarDisplayItem[]>()
  for (const item of items.value) {
    if (!item?.date) continue
    // Episode dates may be full datetimes (broadcast_start); normalize to a plain-date key.
    const dateKey = isoDateKey(item.date)
    if (!dateKey) continue
    const list = map.get(dateKey) || []
    if (item.kind === MEDIA_TYPE.MOVIE) {
      list.push({
        key: `movie-${item.tmdb_id}-${item.date}`,
        kind: MEDIA_TYPE.MOVIE,
        label: item.title,
        sublabel: 'Movie',
        to: `/movies/${item.tmdb_id}`
      })
    } else {
      list.push({
        key: `ep-${item.tmdb_id}-${item.season_number}-${item.episode_number}-${item.date}`,
        kind: item.kind,
        label: item.show_name,
        seasonNumber: item.season_number,
        episodeNumber: item.episode_number,
        airTime: item.air_time || undefined,
        to: `/tv/${item.tmdb_id}/season/${item.season_number}/episode/${item.episode_number}`
      })
    }
    map.set(dateKey, list)
  }
  return map
})

const dayItems = computed(() => itemMap.value.get(anchorIso.value) || [])

const calendarDays = computed(() => {
  if (effectiveViewMode.value === 'week') {
    const bounds = weekBounds(anchorIso.value)
    return bounds ? buildDays(bounds.start, 7) : []
  }

  const bounds = monthBounds(anchorIso.value)
  if (!bounds) {
    return []
  }

  const first = bounds.start
  const startGrid = first.subtract({ days: first.dayOfWeek - 1 })
  return buildDays(startGrid, 42, first)
})

function buildDays(startGrid: TemporalPolyfill.PlainDate, count: number, currentMonthStart: TemporalPolyfill.PlainDate | null = null) {
  const todayIsoValue = todayIso()
  const days: { iso: string; date: TemporalPolyfill.PlainDate; inCurrentMonth: boolean; isToday: boolean; items: CalendarDisplayItem[] }[] = []

  for (let i = 0; i < count; i += 1) {
    const d = startGrid.add({ days: i })
    const iso = d.toString()
    days.push({
      iso,
      date: d,
      inCurrentMonth: !currentMonthStart || (d.month === currentMonthStart.month && d.year === currentMonthStart.year),
      isToday: iso === todayIsoValue,
      items: itemMap.value.get(iso) || []
    })
  }

  return days
}

async function load() {
  loading.value = true
  try {
    if (effectiveViewMode.value === 'day') {
      const anchor = parsePlainDate(anchorIso.value)
      if (!anchor) {
        items.value = []
        return
      }
      const data = await calendarAPI.get({
        start: anchor.toString(),
        days: 1
      })
      items.value = data?.results || []
      return
    }
    const bounds = effectiveViewMode.value === 'week' ? weekBounds(anchorIso.value) : monthBounds(anchorIso.value)
    if (!bounds) {
      items.value = []
      return
    }

    const data = await calendarAPI.get({
      start: bounds.start.toString(),
      days: effectiveViewMode.value === 'week' ? 7 : bounds.end.day
    })
    items.value = data?.results || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function goPrev() {
  await shiftAnchor(-1)
}

async function goNext() {
  await shiftAnchor(1)
}

async function shiftAnchor(direction: number) {
  const anchor = parsePlainDate(anchorIso.value)
  if (!anchor) {
    return
  }
  if (effectiveViewMode.value === 'day') {
    anchorIso.value = anchor.add({ days: direction }).toString()
  } else if (effectiveViewMode.value === 'week') {
    anchorIso.value = anchor.add({ days: 7 * direction }).toString()
  } else {
    anchorIso.value = anchor.with({ day: 1 }).add({ months: direction }).toString()
  }
  await load()
}

async function goToday() {
  anchorIso.value = todayIso()
  await load()
}

async function setViewMode(mode: ViewMode) {
  if (desktopViewMode.value === mode) {
    return
  }
  desktopViewMode.value = mode
  await load()
}

watch(isMobile, async () => {
  await load()
})

onMounted(load)
</script>

<style scoped>
.calendar-grid {
  grid-auto-rows: minmax(min-content, 1fr);
}
</style>
