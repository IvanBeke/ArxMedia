<template>
  <div>
    <div v-if="loading" class="space-y-3">
      <div class="h-4 w-44 skeleton rounded-md"></div>
      <div class="h-[140px] skeleton rounded-md"></div>
    </div>

    <div v-else-if="error" class="text-center py-6">
      <p class="text-muted text-sm mb-3">{{ t('profile_activity_heatmap_error') }}</p>
      <button type="button" class="btn-ghost text-xs border border-surface-200 bg-surface-100/70 hover:bg-surface-100" @click="load">
        Retry
      </button>
    </div>

    <template v-else>
      <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
        <p class="text-sm text-secondary">{{ t('profile_activity_heatmap_total', { count: total }) }}</p>
        <div class="flex items-center gap-1 text-muted">
          <span class="text-[10px] mr-1">{{ t('profile_activity_heatmap_less') }}</span>
          <span v-for="index in 5" :key="index" class="w-3.5 h-3.5 rounded-[3px]" :class="cellClass(index - 1)" />
          <span class="text-[10px] ml-1">{{ t('profile_activity_heatmap_more') }}</span>
        </div>
      </div>

      <div v-if="total === 0" class="text-xs text-muted mb-3">{{ t('profile_activity_heatmap_empty') }}</div>

      <div class="overflow-x-auto pb-1">
        <div class="flex items-start w-max mx-auto">
          <div class="grid shrink-0 mr-1.5" :style="dayLabelGridStyle">
            <span
              v-for="(label, row) in dayLabels"
              :key="row"
              class="text-[9px] text-muted flex items-center"
            >{{ label }}</span>
          </div>
          <div class="shrink-0">
            <div class="grid w-max mb-1.5" :style="monthGridStyle">
              <span
                v-for="(label, col) in monthLabels"
                :key="col"
                class="text-[9px] text-muted whitespace-nowrap flex items-center"
                :style="{ gridColumnStart: col + 1 }"
              >{{ label }}</span>
            </div>
            <div class="grid w-max" :style="dayGridStyle">
              <div v-for="(cell, index) in cells" :key="index" class="relative w-3.5 h-3.5">
                <div
                  v-if="cell"
                  class="w-3.5 h-3.5 rounded-[3px] transition-transform duration-75 hover:scale-125"
                  :class="cellClass(cell.count)"
                  @mouseenter="showPopup(cell, $event)"
                  @mouseleave="scheduleHide"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <Teleport to="body">
        <div
          v-if="popup"
          class="fixed z-50 w-64 card p-3 shadow-xl"
          :style="popupStyle"
          role="tooltip"
          @mouseenter="cancelHide"
          @mouseleave="scheduleHide"
        >
          <p class="text-xs font-medium text-primary mb-2">{{ formatDateByLocale(popup.day.date) }}</p>
          <ul v-if="popup.day.items.length" class="space-y-1.5 max-h-44 overflow-y-auto">
            <li v-for="(item, index) in popup.day.items" :key="index" class="text-xs leading-snug">
              <RouterLink :to="itemLink(item)" class="text-brand-400 hover:text-brand-300 hover:underline">
                {{ itemLabel(item) }}
              </RouterLink>
            </li>
          </ul>
          <p v-else class="text-xs text-muted">{{ t('profile_activity_heatmap_popup_empty') }}</p>
        </div>
      </Teleport>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useCleanupOnUnmount } from '@/composables/useCleanupOnUnmount'
import { authAPI } from '@/api'
import { formatDateByLocale, useI18n } from '@/i18n'
import { formatTemporalDate } from '@/utils/temporal'
import { getEpisodeLink, getMovieLink } from '@/utils/watchEntryLinks'
import type { ActivityDay, ActivityItem } from '@/types/api'

const DAY_CELL_SIZE = 14
const DAY_CELL_GAP = 4
const MONTH_ROW_HEIGHT = DAY_CELL_SIZE
const POPUP_WIDTH = 256
const POPUP_GAP = 6
const POPUP_HIDE_DELAY_MS = 120

const LEVEL_CLASSES = [
  'bg-surface-200',
  'bg-brand-500/25',
  'bg-brand-500/45',
  'bg-brand-500/65',
  'bg-brand-500',
]

const props = defineProps<{ username: string }>()

const { t, locale } = useI18n()

const days = ref<ActivityDay[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref(false)

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await authAPI.getUserActivity(props.username)
    days.value = data.days
    total.value = data.total
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(() => props.username, load)
onMounted(load)

function parseLocalDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year!, month! - 1, day!)
}

// Monday-start offset of the first day in the window (Monday = 0).
const padCount = computed(() => {
  if (!days.value.length) return 0
  return (parseLocalDate(days.value[0]!.date).getDay() + 6) % 7
})

const cells = computed<(ActivityDay | null)[]>(() => [
  ...Array<ActivityDay | null>(padCount.value).fill(null),
  ...days.value,
])

const numCols = computed(() => Math.ceil((padCount.value + days.value.length) / 7))

const localeTag = computed(() => (locale.value === 'es' ? 'es-ES' : 'en-US'))

const monthLabels = computed<string[]>(() => {
  const labels: string[] = []
  let prevMonth = -1
  for (let col = 0; col < numCols.value; col++) {
    let label = ''
    for (let row = 0; row < 7; row++) {
      const cell = cells.value[col * 7 + row]
      if (!cell) continue
      const month = parseLocalDate(cell.date).getMonth()
      if (month !== prevMonth) {
        label = formatTemporalDate(cell.date, localeTag.value, { month: 'short' })
        prevMonth = month
      }
      break
    }
    labels.push(label)
  }
  return labels
})

const dayLabels = computed(() => [
  t('profile_activity_heatmap_day_mon'),
  '',
  t('profile_activity_heatmap_day_wed'),
  '',
  t('profile_activity_heatmap_day_fri'),
  '',
  t('profile_activity_heatmap_day_sun'),
])

// The label column is offset by the month row so labels align with cell rows.
const dayLabelGridStyle = computed(() => ({
  gridTemplateRows: `repeat(7, ${DAY_CELL_SIZE}px)`,
  gap: `${DAY_CELL_GAP}px`,
  marginTop: `${MONTH_ROW_HEIGHT + DAY_CELL_GAP}px`,
}))

const dayGridStyle = computed(() => ({
  gridTemplateRows: `repeat(7, ${DAY_CELL_SIZE}px)`,
  gridAutoFlow: 'column' as const,
  gap: `${DAY_CELL_GAP}px`,
}))

const monthGridStyle = computed(() => ({
  height: `${MONTH_ROW_HEIGHT}px`,
  marginBottom: `${DAY_CELL_GAP}px`,
  gridTemplateColumns: `repeat(${numCols.value}, ${DAY_CELL_SIZE}px)`,
  gap: `${DAY_CELL_GAP}px`,
}))

function cellClass(count: number): string {
  if (count <= 0) return LEVEL_CLASSES[0]!
  if (count >= LEVEL_CLASSES.length - 1) return LEVEL_CLASSES[LEVEL_CLASSES.length - 1]!
  return LEVEL_CLASSES[count]!
}

interface PopupState {
  day: ActivityDay
  below: boolean
}

const popup = ref<PopupState | null>(null)
const popupX = ref(0)
const popupY = ref(0)
let hideTimer: ReturnType<typeof setTimeout> | null = null

const popupStyle = computed(() => ({
  left: `${popupX.value}px`,
  top: `${popupY.value}px`,
  transform: popup.value?.below
    ? `translate(-50%, ${POPUP_GAP}px)`
    : `translate(-50%, calc(-100% - ${POPUP_GAP}px))`,
}))

useCleanupOnUnmount(() => cancelHide())

function cancelHide() {
  if (hideTimer !== null) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function scheduleHide() {
  cancelHide()
  hideTimer = setTimeout(() => {
    popup.value = null
    hideTimer = null
  }, POPUP_HIDE_DELAY_MS)
}

function showPopup(day: ActivityDay, event: MouseEvent) {
  cancelHide()
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const below = rect.top < 190
  popupX.value = Math.min(
    Math.max(rect.left + rect.width / 2, POPUP_WIDTH / 2 + 8),
    window.innerWidth - POPUP_WIDTH / 2 - 8,
  )
  popupY.value = below ? rect.bottom : rect.top
  popup.value = { day, below }
}

function hidePopup() {
  cancelHide()
  popup.value = null
}

function itemLabel(item: ActivityItem): string {
  if (item.media_type === 'movie') {
    return item.release_year ? `${item.title} (${item.release_year})` : item.title
  }
  return `${item.title} ${item.episode_code ?? ''}`.trim()
}

function itemLink(item: ActivityItem): string {
  if (item.media_type === 'movie') return getMovieLink(item.tmdb_id)
  return getEpisodeLink(item.tmdb_id, item.season_number, item.episode_number)
}
</script>
