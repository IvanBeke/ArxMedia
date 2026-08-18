<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-end justify-between gap-3 mb-6">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">Calendar</h1>
        <p class="text-muted text-sm">Watchlist movies and episodes from shows you are watching</p>
      </div>
      <div class="flex gap-2">
        <button class="btn-secondary text-sm" @click="goPrevMonth">Prev</button>
        <button class="btn-secondary text-sm" @click="goToday">Today</button>
        <button class="btn-secondary text-sm" @click="goNextMonth">Next</button>
      </div>
    </div>

    <section class="card p-4">
      <div class="flex items-center justify-between mb-4">
        <h2 class="section-title text-lg">{{ monthLabel }}</h2>
      </div>

      <div class="grid grid-cols-7 gap-2 mb-2">
        <div v-for="weekday in weekdays" :key="weekday" class="text-xs font-medium text-muted text-center py-2">
          {{ weekday }}
        </div>
      </div>

      <div v-if="loading" class="grid grid-cols-7 gap-2">
        <div v-for="n in 42" :key="n" class="h-28 skeleton rounded"></div>
      </div>

      <div v-else class="grid grid-cols-7 gap-2">
        <div
          v-for="day in calendarDays"
          :key="day.iso"
          class="min-h-28 rounded border border-surface-300 p-2"
          :class="day.inCurrentMonth ? 'bg-surface-100/40' : 'bg-surface-200/30 opacity-60'"
        >
          <div class="text-xs mb-2" :class="day.isToday ? 'text-brand-400 font-semibold' : 'text-muted'">
            {{ day.date.getDate() }}
          </div>
          <div class="space-y-1">
            <RouterLink
              v-for="item in day.items.slice(0, 3)"
              :key="item.key"
              :to="item.to"
              class="block text-[11px] leading-snug rounded px-1.5 py-1 bg-surface-200/60 text-primary hover:text-brand-400 truncate"
              :title="item.label"
            >
              <template v-if="item.kind === MEDIA_TYPE.MOVIE">{{ item.label }}</template>
              <template v-else>
                {{ item.showName }}
                <span aria-hidden="true"> </span>
                <EpisodeCodePill
                  :season-number="item.seasonNumber"
                  :episode-number="item.episodeNumber"
                  variant="plain"
                  size="xs"
                />
              </template>
            </RouterLink>
            <p v-if="day.items.length > 3" class="text-[11px] text-muted px-1">+{{ day.items.length - 3 }} more</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { calendarAPI } from '@/api'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'
import { MEDIA_TYPE } from '@/constants/tracking'

function dateToIso(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function addMonths(base, amount) {
  return new Date(base.getFullYear(), base.getMonth() + amount, 1)
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function endOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0)
}

const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const loading = ref(true)
const selectedMonth = ref(startOfMonth(new Date()))
const items = ref([])

const monthLabel = computed(() =>
  selectedMonth.value.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
)

const itemMap = computed(() => {
  const map = new Map()
  for (const item of items.value) {
    if (!item?.date) continue
    const list = map.get(item.date) || []
    if (item.kind === MEDIA_TYPE.MOVIE) {
      list.push({
        key: `movie-${item.tmdb_id}-${item.date}`,
        kind: MEDIA_TYPE.MOVIE,
        label: `Movie: ${item.title}`,
        to: `/movies/${item.tmdb_id}`
      })
    } else {
      list.push({
        key: `ep-${item.tmdb_id}-${item.season_number}-${item.episode_number}-${item.date}`,
        kind: MEDIA_TYPE.TV,
        label: `${item.show_name}`,
        showName: item.show_name,
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
  const first = startOfMonth(selectedMonth.value)
  const last = endOfMonth(selectedMonth.value)
  const firstWeekdayMonBased = (first.getDay() + 6) % 7
  const startGrid = new Date(first)
  startGrid.setDate(first.getDate() - firstWeekdayMonBased)

  const todayIso = dateToIso(new Date())
  const days = []
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(startGrid)
    d.setDate(startGrid.getDate() + i)
    const iso = dateToIso(d)
    days.push({
      iso,
      date: d,
      inCurrentMonth: d.getMonth() === selectedMonth.value.getMonth() && d.getFullYear() === selectedMonth.value.getFullYear(),
      isToday: iso === todayIso,
      items: itemMap.value.get(iso) || []
    })
  }

  if (last < first) {
    return []
  }

  return days
})

async function load() {
  loading.value = true
  try {
    const first = startOfMonth(selectedMonth.value)
    const last = endOfMonth(selectedMonth.value)
    const days = last.getDate()
    const data = await calendarAPI.getMy({
      start: dateToIso(first),
      days
    })
    items.value = data?.results || []
  } catch (error) {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function goPrevMonth() {
  selectedMonth.value = addMonths(selectedMonth.value, -1)
  await load()
}

async function goNextMonth() {
  selectedMonth.value = addMonths(selectedMonth.value, 1)
  await load()
}

async function goToday() {
  selectedMonth.value = startOfMonth(new Date())
  await load()
}

onMounted(load)
</script>
