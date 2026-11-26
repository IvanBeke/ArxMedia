<template>
  <section class="card p-4 md:p-5">
    <h2 class="section-title mb-4">{{ t('stats_watch_time_breakdown') }}</h2>

    <!-- The hidden bar reserves the height of the finished one, so the skeleton, the error, the empty message and
         the bar itself all take the same space and the page does not jump on first load. -->
    <div class="grid">
      <div class="invisible col-start-1 row-start-1" aria-hidden="true">
        <p class="text-xs text-muted mb-3">{{ t('stats_watch_time_all_time') }}</p>
        <StatStackedBar :items="allTimeSpacerSlices" />
      </div>
      <div class="col-start-1 row-start-1 flex flex-col justify-center">
        <StatsState
          :loading="allTime.loading"
          :error="allTime.error"
          skeleton-class="flex-1"
          @retry="retryFailed(allTime)"
        >
          <template v-if="allTimeHasWatchTime">
            <p class="text-xs text-muted mb-3">{{ t('stats_watch_time_all_time') }}</p>
            <StatStackedBar :items="allTimeSlices" />
          </template>
          <p v-else class="text-sm text-muted text-center">{{ t('stats_watch_time_empty') }}</p>
        </StatsState>
      </div>
    </div>

    <div v-if="showYear" class="mt-6">
      <div
        class="flex items-center rounded-lg border border-surface-300 bg-surface-100/60 p-1 w-max mb-4"
        role="group"
        :aria-label="t('stats_year_nav_label')"
      >
        <button
          type="button"
          class="year-button year-step text-muted hover:text-primary hover:bg-surface-200 p-1.5"
          :aria-label="t('stats_prev_year')"
          :disabled="!canGoPrev"
          @click="shiftYear(-1)"
        >
          <ChevronLeft class="w-4 h-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          class="year-button px-3 py-1 mx-0.5 text-sm font-medium tabular-nums text-brand-400 bg-brand-500/10 hover:bg-brand-500/20"
          :aria-label="t('stats_current_year')"
          :disabled="onCurrentYear"
          @click="goToCurrentYear"
        >
          {{ selectedYear ?? '–' }}
        </button>
        <button
          type="button"
          class="year-button year-step text-muted hover:text-primary hover:bg-surface-200 p-1.5"
          :aria-label="t('stats_next_year')"
          :disabled="!canGoNext"
          @click="shiftYear(1)"
        >
          <ChevronRight class="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      <!-- An invisible chart in the same cell keeps the height of the real one, so the skeleton, the messages and the
           chart take the same space and the page does not jump while a year loads. -->
      <div class="grid">
        <StatColumns :items="SPACER_ITEMS" class="invisible col-start-1 row-start-1" aria-hidden="true" />
        <div class="col-start-1 row-start-1 flex flex-col justify-center">
          <StatsState :loading="yearLoading" :error="yearError" skeleton-class="flex-1" @retry="retryFailed(years, monthly)">
            <!-- Keep the previous year's chart on screen while the new one loads, so the bars animate to their new
                 heights instead of being replaced by a skeleton. -->
            <StatColumns
              v-if="yearHasWatchTime"
              :items="monthlyItems"
              class="transition-opacity duration-200 motion-reduce:transition-none"
              :class="{ 'opacity-50': yearStale }"
            />
            <p v-else class="text-sm text-muted text-center">{{ t('stats_watch_time_year_empty', { year: selectedYear }) }}</p>
          </StatsState>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { statsAPI } from '@/api'
import StatColumns from '@/components/StatColumns.vue'
import StatStackedBar from '@/components/StatStackedBar.vue'
import StatsState from '@/components/StatsState.vue'
import { retryFailed, useStatsSection } from '@/composables/useStatsSection'
import { useI18n } from '@/i18n'
import { monthlyColumns, watchTimeSlices } from '@/utils/statsCharts'
import type { WatchTimeStats } from '@/types/api'
import type { StatSliceInput } from '@/types/stats'

const props = defineProps<{
  username: string
  /** The all-time watch time, loaded by the page because its summary cards need it too. */
  allTime: { data: WatchTimeStats | null; loading: boolean; error: boolean; load: () => Promise<void> }
}>()

const SPACER_ITEMS = Array.from({ length: 12 }, (_, index) => ({ key: String(index), label: '–', value: 0 }))

const { t, locale } = useI18n()
const localeTag = computed(() => (locale.value === 'es' ? 'es-ES' : 'en-US'))

// null follows the current year, which is known once `years` has loaded.
const year = ref<number | null>(null)
watch(() => props.username, () => { year.value = null })

const years = useStatsSection(() => props.username, statsAPI.getYears)
const selectedYear = computed(() => year.value ?? years.data?.current_year ?? null)
const monthly = useStatsSection(
  () => props.username,
  (username) => statsAPI.getMonthly(username, selectedYear.value ?? undefined),
  { enabled: () => selectedYear.value !== null, refreshOn: () => selectedYear.value },
)

const canGoPrev = computed(() => {
  const range = years.data
  return !!range && range.earliest_year !== null && selectedYear.value !== null && selectedYear.value > range.earliest_year
})
const canGoNext = computed(() => {
  const range = years.data
  return !!range && selectedYear.value !== null && selectedYear.value < range.current_year
})
const onCurrentYear = computed(() => !years.data || selectedYear.value === years.data.current_year)

function shiftYear(delta: number) {
  if (selectedYear.value !== null) year.value = selectedYear.value + delta
}

function goToCurrentYear() {
  year.value = null
}

const allTimeHasWatchTime = computed(() => (props.allTime.data?.watch_time_minutes ?? 0) > 0)
// Without any watch time at all there is no year to browse.
const showYear = computed(() => !props.allTime.data || allTimeHasWatchTime.value)
// Only the first load shows a skeleton. Once there is a chart, a year change dims it in place while new data arrives.
const yearLoading = computed(() => years.loading || (monthly.loading && !monthly.data))
const yearStale = computed(() => (monthly.loading || years.loading) && !!monthly.data)
const yearError = computed(() => years.error || monthly.error)
const yearHasWatchTime = computed(() => monthly.data?.months.some((month) => month.movie_minutes + month.episode_minutes > 0) ?? false)

const allTimeSlices = computed(() => (props.allTime.data ? watchTimeSlices(props.allTime.data, t) : []))
const allTimeSpacerSlices = computed<StatSliceInput[]>(() =>
  allTimeSlices.value.length
    ? allTimeSlices.value
    : [
        { key: 'movies', label: t('history_filter_movies'), value: 1, colorClass: 'text-blue-500', display: '0m' },
        { key: 'episodes', label: t('history_filter_episodes'), value: 1, colorClass: 'text-brand-500', display: '0m' },
      ],
)
const monthlyItems = computed(() => (monthly.data ? monthlyColumns(monthly.data.months, t, localeTag.value) : []))
</script>

<style scoped>
@reference "../assets/main.css";

.year-button {
  @apply rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-default;
}

/* A step that cannot go further fades out; the year in the middle keeps its colour when it has nothing to jump to. */
.year-step {
  @apply disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted;
}

.year-button:not(.year-step) {
  @apply disabled:hover:bg-brand-500/10;
}
</style>
