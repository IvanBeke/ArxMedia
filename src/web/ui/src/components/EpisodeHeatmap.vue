<template>
  <div>
    <div v-if="loading" class="space-y-3">
      <div v-for="n in 4" :key="n" class="h-10 skeleton rounded-md"></div>
    </div>

    <div v-else-if="error" class="card p-6 text-center">
      <p class="text-muted text-sm mb-3">Failed to load episode ratings.</p>
      <button type="button" class="btn-ghost text-xs border border-surface-200 bg-surface-100/70 hover:bg-surface-100" @click="load">
        Retry
      </button>
    </div>

    <div v-else-if="!seasons.length" class="card p-6 text-center">
      <p class="text-muted text-sm">No episode ratings available.</p>
    </div>

    <div v-else class="relative">
      <div ref="scrollContainer" class="overflow-x-auto" @scroll="updateOverflow">
      <!-- Desktop/tablet: rows = seasons, columns = episodes -->
      <table class="hidden md:table w-max border-separate" style="border-spacing: 3px">
        <thead>
          <tr>
            <th class="w-10"></th>
            <th
              v-for="epNum in maxEpisodes"
              :key="epNum"
              class="text-muted text-xs font-normal text-center w-8"
            >
              E{{ epNum }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="season in seasons" :key="season.season">
            <td class="text-muted text-xs font-normal text-right pr-2">S{{ season.season }}</td>
            <td
              v-for="epNum in maxEpisodes"
              :key="epNum"
              class="text-center text-sm font-bold rounded-md w-8 h-8"
              :class="getCellClass(getRating(season, epNum))"
            >
              {{ getRatingLabel(getRating(season, epNum)) }}
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Mobile: rows = episodes, columns = seasons -->
      <table class="md:hidden table w-max border-separate" style="border-spacing: 3px">
        <thead>
          <tr>
            <th class="w-10"></th>
            <th
              v-for="season in seasons"
              :key="season.season"
              class="text-muted text-xs font-normal text-center"
            >
              S{{ season.season }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="epNum in maxEpisodes" :key="epNum">
            <td class="text-muted text-xs font-normal text-right pr-2">E{{ epNum }}</td>
            <td
              v-for="season in seasons"
              :key="season.season"
              class="text-center text-sm font-bold rounded-md h-8"
              :class="getCellClass(getRating(season, epNum))"
            >
              {{ getRatingLabel(getRating(season, epNum)) }}
            </td>
          </tr>
        </tbody>
      </table>
      </div>

      <div
        v-show="overflowLeft"
        class="absolute left-0 top-0 bottom-0 w-8 pointer-events-none"
        style="background: linear-gradient(to right, var(--bg-primary), transparent)"
      ></div>
      <div
        v-show="overflowRight"
        class="absolute right-0 top-0 bottom-0 w-8 pointer-events-none"
        style="background: linear-gradient(to left, var(--bg-primary), transparent)"
      ></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { mediaAPI } from '@/api'
import { formatRating } from '@/utils/format'
import type { HeatmapSeason } from '@/types/api'

const props = defineProps<{
  showId: number
}>()

const seasons = ref<HeatmapSeason[]>([])
const loading = ref(true)
const error = ref(false)
const scrollContainer = ref<HTMLElement | null>(null)
const overflowLeft = ref(false)
const overflowRight = ref(false)

const maxEpisodes = computed(() => {
  return seasons.value.reduce((max, s) => {
    return Math.max(max, ...s.episodes.map(e => e.episode))
  }, 0)
})

function getRating(season: HeatmapSeason, episodeNum: number): number {
  const ep = season.episodes.find((e) => e.episode === episodeNum)
  return ep?.rating ?? 0
}

function getRatingLabel(rating: number): string {
  if (!rating) return ''
  return formatRating(rating)
}

const CELL_COLORS: Record<number, string> = {
  0: 'bg-surface-300/50 text-black',
  1: 'bg-[#b01030] text-black',
  2: 'bg-[#cc0000] text-black',
  3: 'bg-[#cc3700] text-black',
  4: 'bg-[#cc7000] text-black',
  5: 'bg-[#cc8400] text-black',
  6: 'bg-[#cccc00] text-black',
  7: 'bg-[#7ba428] text-black',
  8: 'bg-[#64c800] text-black',
  9: 'bg-[#28a428] text-black',
  10: 'bg-[#1a6e1a] text-black',
}

function getCellClass(rating: number): string {
  if (!rating) return CELL_COLORS[0]!
  const int = Math.trunc(Number(formatRating(rating)))
  return CELL_COLORS[int]!
}

function updateOverflow() {
  const el = scrollContainer.value
  if (!el) return
  overflowLeft.value = el.scrollLeft > 0
  overflowRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth
}

async function load() {
  loading.value = true
  error.value = false
  try {
    seasons.value = await mediaAPI.getTVHeatmap(props.showId)
    requestAnimationFrame(updateOverflow)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', updateOverflow)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateOverflow)
})
</script>
