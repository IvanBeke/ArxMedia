<template>
  <div>
    <!-- Hero -->
    <section class="relative overflow-hidden min-h-[60vh] flex items-center">
      <div class="absolute inset-0 z-0">
        <div
          v-if="heroBackdrop"
          class="w-full h-full bg-cover bg-center"
          :style="`background-image: url(${heroBackdrop})`"
        ></div>
        <div class="absolute inset-0 bg-gradient-to-b from-surface via-surface/70 to-surface"></div>
        <div class="absolute inset-0 bg-gradient-to-r from-surface/90 to-transparent"></div>
      </div>

      <div class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div class="max-w-xl">
          <div class="inline-flex items-center gap-2 mb-4 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs">
            <span class="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse"></span>
            Track · Rate · Discover
          </div>
          <h1 class="font-display text-5xl md:text-7xl text-primary font-semibold leading-tight mb-4">
            Never lose track of<br />what you're <span class="text-brand-500">watching</span>
          </h1>
          <p class="text-muted text-base mb-6">
            Track every movie and TV show. Rate them, review them, and discover what to watch next with the community.
          </p>
          <div class="flex gap-3">
            <RouterLink to="/register" class="btn-primary px-5 py-2.5 text-sm">
              Sign Up — It's Free
            </RouterLink>
            <RouterLink to="/search" class="btn-ghost px-5 py-2.5 text-sm">
              Browse Content
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- Trending -->
    <section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div class="flex items-center justify-between mb-6">
        <h2 class="section-title">Trending</h2>
        <div class="flex gap-1">
          <button
            v-for="t in ['all', MEDIA_TYPE.MOVIE, MEDIA_TYPE.TV]"
            :key="t"
            @click="trendingType = t"
            class="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            :class="trendingType === t ? 'bg-brand-500 text-white' : 'text-muted hover:text-primary hover:bg-surface-100'"
          >
            {{ t === 'all' ? 'All' : t === MEDIA_TYPE.MOVIE ? 'Movies' : 'TV Shows' }}
          </button>
        </div>
      </div>

      <div v-if="loadingTrending" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div v-for="n in 12" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
      </div>

      <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <MediaCard
          v-for="item in trending"
          :key="item.id"
          :item="item"
          :media-type="item.media_type || MEDIA_TYPE.MOVIE"
        />
      </div>

      <div v-if="loadingRecommendations" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 mt-8">
        <div v-for="n in 6" :key="`rec-skel-${n}`" class="aspect-[2/3] rounded-md skeleton"></div>
      </div>
      <div v-else-if="recommendations.movies.length || recommendations.tv.length" class="mt-8 space-y-6">
        <div v-if="recommendations.movies.length">
          <h3 class="section-title mb-3 text-lg">Recommended Movies</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <MediaCard v-for="item in recommendations.movies" :key="`home-rec-m-${item.id}`" :item="item" :media-type="MEDIA_TYPE.MOVIE" />
          </div>
        </div>
        <div v-if="recommendations.tv.length">
          <h3 class="section-title mb-3 text-lg">Recommended TV Shows</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <MediaCard v-for="item in recommendations.tv" :key="`home-rec-t-${item.id}`" :item="item" :media-type="MEDIA_TYPE.TV" />
          </div>
        </div>
      </div>
    </section>

    <!-- Popular Movies -->
    <section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div class="flex items-center justify-between mb-6">
        <h2 class="section-title">Popular Movies</h2>
        <RouterLink to="/search?type=movie" class="text-brand-500 hover:text-brand-400 text-xs font-medium">View all →</RouterLink>
      </div>
      <div v-if="loadingPopular" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div v-for="n in 6" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
      </div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <MediaCard
          v-for="item in popularMovies"
          :key="item.id"
          :item="item"
          :media-type="MEDIA_TYPE.MOVIE"
        />
      </div>
    </section>

    <!-- Popular TV -->
    <section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-20">
      <div class="flex items-center justify-between mb-6">
        <h2 class="section-title">Popular TV Shows</h2>
        <RouterLink to="/search?type=tv" class="text-brand-500 hover:text-brand-400 text-xs font-medium">View all →</RouterLink>
      </div>
      <div v-if="loadingPopularTV" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div v-for="n in 6" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
      </div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <MediaCard
          v-for="item in popularTV"
          :key="item.id"
          :item="item"
          :media-type="MEDIA_TYPE.TV"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { mediaAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import MediaCard from '@/components/MediaCard.vue'
import { MEDIA_TYPE } from '@/constants/tracking'

const trending = ref([])
const popularMovies = ref([])
const popularTV = ref([])
const trendingType = ref('all')
const loadingTrending = ref(true)
const loadingPopular = ref(true)
const loadingPopularTV = ref(true)
const recommendations = ref({ movies: [], tv: [] })
const loadingRecommendations = ref(true)
const auth = useAuthStore()

const heroBackdrop = computed(() => {
  const item = trending.value[0]
  if (!item?.backdrop_path) return null
  return `https://image.tmdb.org/t/p/w1280${item.backdrop_path}`
})

async function loadTrending() {
  loadingTrending.value = true
  try {
    const data = await mediaAPI.trending(trendingType.value)
    if (data) {
      trending.value = data.results?.slice(0, 12) || []
    }
  } finally {
    loadingTrending.value = false
  }
}

onMounted(async () => {
  loadingTrending.value = true
  const requests = [
    mediaAPI.trending(trendingType.value),
    mediaAPI.popular(MEDIA_TYPE.MOVIE),
    mediaAPI.popular(MEDIA_TYPE.TV),
  ]
  if (auth.isAuthenticated) {
    requests.push(trackingAPI.getRecommendations())
  }

  const results = await Promise.allSettled(requests)
  const [trendingRes, moviesRes, tvRes, recsRes] = results

  if (trendingRes?.status === 'fulfilled') {
    const data = trendingRes.value
    trending.value = data?.results?.slice(0, 12) || []
  }
  loadingTrending.value = false

  if (moviesRes?.status === 'fulfilled') {
    popularMovies.value = moviesRes.value?.results?.slice(0, 6) || []
  }
  loadingPopular.value = false

  if (tvRes?.status === 'fulfilled') {
    popularTV.value = tvRes.value?.results?.slice(0, 6) || []
  }
  loadingPopularTV.value = false

  if (auth.isAuthenticated && recsRes?.status === 'fulfilled') {
    recommendations.value = {
      movies: recsRes.value?.movies || [],
      tv: recsRes.value?.tv || []
    }
  }
  loadingRecommendations.value = false
})

watch(trendingType, loadTrending)
</script>
