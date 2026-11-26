import { vi } from 'vitest'
import { statsAPI } from '@/api'
import type { HabitsStats, LibraryStats, MonthlyStats, RatingStats, WatchCountStats, WatchTimeStats, YearsStats } from '@/types/api'

export function ratingStats(overrides: Partial<RatingStats> = {}): RatingStats {
  return {
    ratings_count: 4,
    average_rating: 8,
    rating_distribution: [0, 0, 0, 0, 0, 0, 1, 2, 0, 1],
    ...overrides,
  }
}

export function libraryStats(overrides: Partial<LibraryStats> = {}): LibraryStats {
  return {
    show_statuses: { plan_to_watch: 1, watching: 2, watched: 3, dropped: 0 },
    movie_statuses: { plan_to_watch: 2, watched: 10, dropped: 1 },
    media_types: { movie: 13, tv: 6 },
    watchlist_count: 3,
    ...overrides,
  }
}

export function watchCountStats(overrides: Partial<WatchCountStats> = {}): WatchCountStats {
  return { movies_watched: 12, episodes_watched: 40, ...overrides }
}

export function watchTimeStats(overrides: Partial<WatchTimeStats> = {}): WatchTimeStats {
  return {
    movie_minutes: 100,
    episode_minutes: 50,
    watch_time_minutes: 150,
    ...overrides,
  }
}

export function monthlyStats(overrides: Partial<MonthlyStats> = {}): MonthlyStats {
  return {
    year: 2026,
    months: Array.from({ length: 12 }, (_, index) => ({
      month: `2026-${String(index + 1).padStart(2, '0')}`,
      movie_minutes: index === 11 ? 100 : 0,
      episode_minutes: index === 11 ? 50 : 0,
    })),
    ...overrides,
  }
}

export function yearsStats(overrides: Partial<YearsStats> = {}): YearsStats {
  return { current_year: 2026, earliest_year: 2024, ...overrides }
}

export function habitsStats(overrides: Partial<HabitsStats> = {}): HabitsStats {
  return {
    movie: { weekdays: [1, 0, 2, 0, 0, 0, 3], hours: Array.from({ length: 24 }, (_, hour) => (hour === 21 ? 4 : hour === 0 ? 2 : 0)) },
    episode: { weekdays: [5, 4, 3, 2, 1, 0, 0], hours: Array.from({ length: 24 }, (_, hour) => (hour === 20 ? 9 : 0)) },
    ...overrides,
  }
}

/** Spies on every stats endpoint, answering with the default fixtures unless overridden. */
export function mockStatsAPI() {
  return {
    ratings: vi.spyOn(statsAPI, 'getRatings').mockResolvedValue(ratingStats()),
    library: vi.spyOn(statsAPI, 'getLibrary').mockResolvedValue(libraryStats()),
    watchCount: vi.spyOn(statsAPI, 'getWatchCount').mockResolvedValue(watchCountStats()),
    watchTime: vi.spyOn(statsAPI, 'getWatchTime').mockResolvedValue(watchTimeStats()),
    monthly: vi.spyOn(statsAPI, 'getMonthly').mockResolvedValue(monthlyStats()),
    years: vi.spyOn(statsAPI, 'getYears').mockResolvedValue(yearsStats()),
    habits: vi.spyOn(statsAPI, 'getHabits').mockResolvedValue(habitsStats()),
  }
}
