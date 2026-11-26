<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-6">
      <RouterLink :to="`/profile/${username}`" class="text-muted text-sm hover:text-brand-400 transition inline-flex items-center gap-1 mb-3">
        <ChevronLeft class="w-4 h-4" aria-hidden="true" />
        {{ t('profile_back_to_profile') }}
      </RouterLink>
      <h1 class="font-display text-2xl text-primary font-semibold">{{ t('stats_title') }}</h1>
    </div>

    <div v-if="locked" class="card p-6 text-sm text-muted">{{ t('stats_locked') }}</div>

    <div v-else class="space-y-6">
      <div v-if="cardsLoading" class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div v-for="n in 8" :key="n" class="h-[74px] skeleton rounded-lg"></div>
      </div>
      <LoadError v-else-if="cardsError" :message="t('error_load_stats')" @retry="retryFailed(watchCount, watchTime, library, ratings)" />
      <UserStatCards
        v-else-if="watchCount.data && watchTime.data && library.data && ratings.data"
        :watch-count="watchCount.data"
        :watch-time="watchTime.data"
        :library="library.data"
        :ratings="ratings.data"
      />

      <StatsSection :title="t('stats_statuses')" :loading="library.loading" :error="library.error" @retry="retryFailed(library)">
        <div v-if="hasMediaTypes" class="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10">
          <div>
            <p class="text-xs text-muted mb-3">{{ t('filter_bar_media_shows') }}</p>
            <StatPie v-if="hasShows" :items="showStatusItems" />
            <p v-else class="text-sm text-muted">{{ t('stats_library_empty') }}</p>
          </div>
          <div>
            <p class="text-xs text-muted mb-3">{{ t('history_filter_movies') }}</p>
            <StatPie v-if="hasMovies" :items="movieStatusItems" />
            <p v-else class="text-sm text-muted">{{ t('stats_library_empty') }}</p>
          </div>
        </div>
        <p v-else class="text-sm text-muted">{{ t('stats_library_empty') }}</p>
      </StatsSection>

      <WatchTimeSection :username="username" :all-time="watchTime" />

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <StatsSection :title="t('stats_rating_distribution')" :loading="ratings.loading" :error="ratings.error" @retry="retryFailed(ratings)">
          <StatColumns v-if="hasRatings" :items="ratingItems" />
          <p v-else class="text-sm text-muted">{{ t('stats_rating_distribution_empty') }}</p>
        </StatsSection>

        <StatsSection :title="t('stats_media_types')" :loading="library.loading" :error="library.error" @retry="retryFailed(library)">
          <StatPie v-if="hasMediaTypes" :items="mediaTypeItems" />
          <p v-else class="text-sm text-muted">{{ t('stats_library_empty') }}</p>
        </StatsSection>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <StatsSection
          v-for="chart in habitChartItems"
          :key="chart.key"
          :title="chart.title"
          :loading="habits.loading"
          :error="habits.error"
          :class="{ 'lg:col-span-2': chart.fullRow }"
          @retry="retryFailed(habits)"
        >
          <StatColumns v-if="chart.hasData" compact :items="chart.items" :bar-class="chart.barClass" />
          <p v-else class="text-sm text-muted">{{ t('stats_watch_activity_empty') }}</p>
        </StatsSection>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronLeft } from '@lucide/vue'
import { statsAPI } from '@/api'
import LoadError from '@/components/LoadError.vue'
import StatColumns from '@/components/StatColumns.vue'
import StatPie from '@/components/StatPie.vue'
import StatsSection from '@/components/StatsSection.vue'
import UserStatCards from '@/components/UserStatCards.vue'
import WatchTimeSection from '@/components/WatchTimeSection.vue'
import { usePageTitle } from '@/composables/usePageTitle'
import { retryFailed, useStatsSection } from '@/composables/useStatsSection'
import { useI18n } from '@/i18n'
import {
  habitCharts,
  mediaTypeSlices,
  movieStatusSlices,
  ratingColumns,
  showStatusSlices,
} from '@/utils/statsCharts'

const route = useRoute()
const { t, locale } = useI18n()

const username = computed(() => String(route.params.username ?? ''))
usePageTitle(() => t('stats_title'))

const ratings = useStatsSection(() => username.value, statsAPI.getRatings)
const library = useStatsSection(() => username.value, statsAPI.getLibrary)
const watchCount = useStatsSection(() => username.value, statsAPI.getWatchCount)
const watchTime = useStatsSection(() => username.value, statsAPI.getWatchTime)
const habits = useStatsSection(() => username.value, statsAPI.getHabits)

const locked = computed(() => [ratings, library, watchCount, watchTime, habits].some((section) => section.forbidden))
const cardsLoading = computed(() => watchCount.loading || watchTime.loading || library.loading || ratings.loading)
const cardsError = computed(() => watchCount.error || watchTime.error || library.error || ratings.error)

const localeTag = computed(() => (locale.value === 'es' ? 'es-ES' : 'en-US'))

const hasRatings = computed(() => (ratings.data?.ratings_count ?? 0) > 0)
const hasShows = computed(() => (library.data?.media_types.tv ?? 0) > 0)
const hasMovies = computed(() => (library.data?.media_types.movie ?? 0) > 0)
const hasMediaTypes = computed(() => hasShows.value || hasMovies.value)

const ratingItems = computed(() => (ratings.data ? ratingColumns(ratings.data.rating_distribution) : []))
const showStatusItems = computed(() => (library.data ? showStatusSlices(library.data.show_statuses, t) : []))
const movieStatusItems = computed(() => (library.data ? movieStatusSlices(library.data.movie_statuses, t) : []))
const mediaTypeItems = computed(() => (library.data ? mediaTypeSlices(library.data.media_types, t) : []))
const habitChartItems = computed(() => habitCharts(habits.data, t, localeTag.value))
</script>
