<template>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <StatCard v-for="card in cards" :key="card.key" :value="card.value" :title="card.title" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatCard from '@/components/StatCard.vue'
import { useI18n } from '@/i18n'
import { formatHoursMinutes } from '@/utils/progress'
import type { LibraryStats, RatingStats, WatchCountStats, WatchTimeStats } from '@/types/api'

const props = defineProps<{
  watchCount: WatchCountStats
  watchTime: WatchTimeStats
  ratings: RatingStats
  /** Without it only the four headline cards are shown. */
  library?: LibraryStats
}>()

const { t } = useI18n()

const cards = computed(() => {
  const { watchCount, ratings, library } = props
  const movies = { key: 'movies', title: t('stats_movies_watched'), value: watchCount.movies_watched }
  const episodes = { key: 'episodes', title: t('stats_episodes_watched'), value: watchCount.episodes_watched }
  const watchTime = { key: 'watch_time', title: t('stats_watch_time'), value: formatHoursMinutes(props.watchTime.watch_time_minutes, false, t) }
  const avgRating = { key: 'avg_rating', title: t('stats_avg_rating'), value: ratings.average_rating ?? '–' }
  if (!library) return [movies, episodes, watchTime, avgRating]
  return [
    movies,
    { key: 'shows', title: t('stats_shows_watched'), value: library.show_statuses.watched },
    episodes,
    { key: 'watching', title: t('stats_shows_watching'), value: library.show_statuses.watching },
    watchTime,
    { key: 'ratings', title: t('stats_ratings'), value: ratings.ratings_count },
    { key: 'watchlist', title: t('page_watchlist'), value: library.watchlist_count },
    avgRating,
  ]
})
</script>
