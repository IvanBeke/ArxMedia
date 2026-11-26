import { MEDIA_COLOR, STATUS_COLOR } from '@/constants/statColors'
import { formatHoursMinutes } from '@/utils/progress'
import { formatTemporalDate } from '@/utils/temporal'
import type { useI18n, MessageKey } from '@/i18n'
import type { HabitsStats, LibraryStats, MonthlyStats, WatchHabits, WatchTimeStats } from '@/types/api'
import type { StatColumnItem, StatSliceInput } from '@/types/stats'

type Translate = ReturnType<typeof useI18n>['t']
type StatusKey = keyof typeof STATUS_COLOR

const MINUTES_PER_HOUR = 60
const STATUS_LABEL_KEY = {
  watching: 'watch_action_watching',
  watched: 'watch_action_watched',
  plan_to_watch: 'status_plan_to_watch',
  dropped: 'watch_action_dropped',
} as const satisfies Record<StatusKey, MessageKey>
const SHOW_STATUS_ORDER = ['watching', 'watched', 'plan_to_watch', 'dropped'] as const
const MOVIE_STATUS_ORDER = ['watched', 'plan_to_watch', 'dropped'] as const
// 2024-01-01 is a Monday, so these dates give the weekday names in ISO (Monday first) order.
const MONDAY_BASED_WEEK_START = '2024-01-0'
const NO_HABITS: WatchHabits = { weekdays: [], hours: [] }

function statusSlices<K extends StatusKey>(counts: Record<K, number>, order: readonly K[], t: Translate): StatSliceInput[] {
  return order.map((status) => ({
    key: status,
    label: t(STATUS_LABEL_KEY[status]),
    value: counts[status],
    colorClass: STATUS_COLOR[status].text,
  }))
}

export function showStatusSlices(statuses: LibraryStats['show_statuses'], t: Translate): StatSliceInput[] {
  return statusSlices(statuses, SHOW_STATUS_ORDER, t)
}

export function movieStatusSlices(statuses: LibraryStats['movie_statuses'], t: Translate): StatSliceInput[] {
  return statusSlices(statuses, MOVIE_STATUS_ORDER, t)
}

export function mediaTypeSlices(types: LibraryStats['media_types'], t: Translate): StatSliceInput[] {
  return [
    { key: 'movie', label: t('history_filter_movies'), value: types.movie, colorClass: MEDIA_COLOR.movie.text },
    { key: 'tv', label: t('filter_bar_media_shows'), value: types.tv, colorClass: MEDIA_COLOR.tv.text },
  ]
}

export function watchTimeSlices(watchTime: WatchTimeStats, t: Translate): StatSliceInput[] {
  return [
    { key: 'movies', label: t('history_filter_movies'), value: watchTime.movie_minutes, colorClass: MEDIA_COLOR.movie.text, display: formatHoursMinutes(watchTime.movie_minutes, false, t) },
    { key: 'episodes', label: t('history_filter_episodes'), value: watchTime.episode_minutes, colorClass: MEDIA_COLOR.tv.text, display: formatHoursMinutes(watchTime.episode_minutes, false, t) },
  ]
}

export function ratingColumns(distribution: number[]): StatColumnItem[] {
  return distribution.map((count, index) => ({ key: String(index + 1), label: String(index + 1), value: count }))
}

export function monthlyColumns(months: MonthlyStats['months'], t: Translate, locale: string): StatColumnItem[] {
  return months.map(({ month, movie_minutes: movies, episode_minutes: episodes }) => {
    const total = movies + episodes
    const monthStart = `${month}-01`
    const monthName = formatTemporalDate(monthStart, locale, { month: 'long', year: 'numeric' })
    return {
      key: month,
      label: formatTemporalDate(monthStart, locale, { month: 'short' }),
      value: total,
      display: `${Math.max(1, Math.round(total / MINUTES_PER_HOUR))}h`,
      title: `${monthName}: ${t('history_filter_movies')} ${formatHoursMinutes(movies, false, t)} · ${t('history_filter_episodes')} ${formatHoursMinutes(episodes, false, t)}`,
      segments: [
        { value: episodes, barClass: MEDIA_COLOR.tv.bg },
        { value: movies, barClass: MEDIA_COLOR.movie.bg },
      ],
    }
  })
}

function weekdayColumns(counts: number[], locale: string): StatColumnItem[] {
  return counts.map((count, index) => {
    const date = `${MONDAY_BASED_WEEK_START}${index + 1}`
    return {
      key: String(index),
      label: formatTemporalDate(date, locale, { weekday: 'short' }),
      value: count,
      title: `${formatTemporalDate(date, locale, { weekday: 'long' })}: ${count}`,
    }
  })
}

function hourColumns(counts: number[]): StatColumnItem[] {
  return counts.map((count, hour) => {
    const label = String(hour).padStart(2, '0')
    return { key: label, label, value: count, title: `${label}:00: ${count}` }
  })
}

/** The four by-day and by-time charts; without data they are empty, so the page can show their shells while loading. */
export function habitCharts(habits: HabitsStats | null, t: Translate, locale: string) {
  const { movie, episode } = habits ?? { movie: NO_HABITS, episode: NO_HABITS }
  const charts = [
    { key: 'movies-day', title: t('stats_movies_by_day'), counts: movie.weekdays, barClass: MEDIA_COLOR.movie.bg, columns: (counts: number[]) => weekdayColumns(counts, locale), fullRow: false },
    { key: 'episodes-day', title: t('stats_episodes_by_day'), counts: episode.weekdays, barClass: MEDIA_COLOR.tv.bg, columns: (counts: number[]) => weekdayColumns(counts, locale), fullRow: false },
    { key: 'movies-time', title: t('stats_movies_by_time'), counts: movie.hours, barClass: MEDIA_COLOR.movie.bg, columns: hourColumns, fullRow: true },
    { key: 'episodes-time', title: t('stats_episodes_by_time'), counts: episode.hours, barClass: MEDIA_COLOR.tv.bg, columns: hourColumns, fullRow: true },
  ]
  return charts.map(({ columns, counts, ...chart }) => ({
    ...chart,
    items: columns(counts),
    hasData: counts.some((count) => count > 0),
  }))
}
