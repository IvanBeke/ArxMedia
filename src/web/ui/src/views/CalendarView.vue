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
            :aria-label="viewMode === 'week' ? 'Previous week' : 'Previous month'"
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
            :aria-label="viewMode === 'week' ? 'Next week' : 'Next month'"
            @click="goNext"
          >
            <ChevronRight class="w-4 h-4" />
          </button>
        </div>
        <h2 class="section-title text-lg text-center truncate">{{ periodLabel }}</h2>
        <div
          class="flex items-center rounded-lg border border-surface-300 bg-surface-100/60 p-0.5"
          role="group"
          aria-label="Calendar view mode"
        >
          <button
            v-for="mode in viewModes"
            :key="mode.value"
            class="px-3 py-1 text-sm rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
            :class="viewMode === mode.value ? 'bg-brand-500 text-white shadow-sm' : 'text-muted hover:text-primary'"
            :aria-pressed="viewMode === mode.value"
            @click="setViewMode(mode.value)"
          >
            {{ mode.label }}
          </button>
        </div>
      </div>

      <div class="grid grid-cols-7 gap-2 mb-2">
        <div v-for="weekday in weekdays" :key="weekday" class="text-xs font-medium text-muted text-center py-2">
          {{ weekday }}
        </div>
      </div>

      <div v-if="loading" class="grid grid-cols-7 gap-2 flex-1">
        <div v-for="n in skeletonCount" :key="n" class="min-h-28 skeleton rounded"></div>
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
                <template v-else>{{ item.sublabel }}</template>
              </span>
            </RouterLink>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { calendarAPI } from '@/api'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { monthBounds, parsePlainDate, weekBounds } from '@/utils/temporal'

function todayIso() {
  return Temporal.Now.plainDateISO().toString()
}

const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const viewModes = [
  { value: 'month', label: 'Month' },
  { value: 'week', label: 'Week' },
]
const loading = ref(true)
const viewMode = ref('month')
const anchorIso = ref(todayIso())
const items = ref([])

const skeletonCount = computed(() => (viewMode.value === 'week' ? 7 : 42))

const periodLabel = computed(() => {
  if (viewMode.value === 'week') {
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
  const map = new Map()
  for (const item of items.value) {
    if (!item?.date) continue
    const list = map.get(item.date) || []
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
        kind: MEDIA_TYPE.TV,
        label: item.show_name,
        seasonNumber: item.season_number,
        episodeNumber: item.episode_number,
        to: `/tv/${item.tmdb_id}/season/${item.season_number}/episode/${item.episode_number}`
      })
    }
    map.set(item.date, list)
  }
  return map
})

const calendarDays = computed(() => {
  if (viewMode.value === 'week') {
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

function buildDays(startGrid, count, currentMonthStart = null) {
  const todayIsoValue = todayIso()
  const days = []

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
    const bounds = viewMode.value === 'week' ? weekBounds(anchorIso.value) : monthBounds(anchorIso.value)
    if (!bounds) {
      items.value = []
      return
    }

    const data = await calendarAPI.get({
      start: bounds.start.toString(),
      days: viewMode.value === 'week' ? 7 : bounds.end.day
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

async function shiftAnchor(direction) {
  const anchor = parsePlainDate(anchorIso.value)
  if (!anchor) {
    return
  }
  anchorIso.value = (
    viewMode.value === 'week'
      ? anchor.add({ days: 7 * direction })
      : anchor.with({ day: 1 }).add({ months: direction })
  ).toString()
  await load()
}

async function goToday() {
  anchorIso.value = todayIso()
  await load()
}

async function setViewMode(mode) {
  if (viewMode.value === mode) {
    return
  }
  viewMode.value = mode
  await load()
}

onMounted(load)
</script>

<style scoped>
.calendar-grid {
  grid-auto-rows: minmax(min-content, 1fr);
}
</style>
