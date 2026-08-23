<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="font-display text-2xl text-primary font-semibold mb-6">{{ pageTitle }}</h1>

    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

    <div class="mb-6">
      <SearchBar
        v-model="query"
        :scope="activeScope"
        :autofocus="true"
        :enable-preview="false"
        :inline-scope-selector="true"
        placeholder="Search movies, series & anime, or #id"
        @update:scope="setScope"
        @submit="onSearchSubmit"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <div v-for="n in 10" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
    </div>

    <!-- Results -->
    <UserList
      v-else-if="isUserScope && userResults.length"
      :users="userResults"
      :followers-label="t('profile_followers_count_label')"
      :following-label="t('profile_following_count_label')"
    />

    <div v-else-if="results.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <MediaCard
        v-for="item in results"
        :key="`${item.media_type}-${item.id}`"
        :item="item"
        :media-type="item.media_type || MEDIA_TYPE.MOVIE"
        @error="showQuickActionError"
      />
    </div>

    <!-- Empty state -->
    <div v-else-if="query && !loading" class="text-center py-20 text-gray-500">
      <p class="text-lg">No results for "{{ query }}"</p>
    </div>

    <!-- Default state -->
    <div v-else-if="!query && !isUserScope">
      <h2 class="section-title mb-4">Trending Right Now</h2>
      <div v-if="loadingDefault" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <div v-for="n in 10" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
      </div>
      <div v-else class="space-y-8">
        <div v-if="(activeFilter === 'multi' || activeFilter === MEDIA_TYPE.MOVIE) && trendingMovies.length">
          <h3 class="section-title mb-4">Movies</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <MediaCard
              v-for="item in trendingMovies"
              :key="`movie-${item.id}`"
              :item="item"
              :media-type="MEDIA_TYPE.MOVIE"
              @error="showQuickActionError"
            />
          </div>
        </div>

        <div v-if="(activeFilter === 'multi' || activeFilter === MEDIA_TYPE.TV) && trendingTvShows.length">
          <h3 class="section-title mb-4">TV Shows</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <MediaCard
              v-for="item in trendingTvShows"
              :key="`tv-${item.id}`"
              :item="item"
              :media-type="MEDIA_TYPE.TV"
              @error="showQuickActionError"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!query && isUserScope" class="card p-6 text-sm text-muted">
      Search users by username.
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authAPI, mediaAPI } from '@/api'
import MediaCard from '@/components/MediaCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import UserList from '@/components/UserList.vue'
import { useAuthStore } from '@/stores/auth'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useI18n } from '@/i18n'
import { useFlashMessages } from '@/composables/useFlashMessages'

const route = useRoute()
const router = useRouter()
const query = ref('')
const results = ref([])
const userResults = ref([])
const trendingMovies = ref([])
const trendingTvShows = ref([])
const loading = ref(false)
const loadingDefault = ref(true)
const activeFilter = ref('multi')
const { errorMsg: quickActionError, showError: showQuickActionError } = useFlashMessages()
const auth = useAuthStore()
const { t } = useI18n()

const SCOPE_VALUE = Object.freeze({
  ALL: 'all',
  MOVIES: 'movies',
  SHOWS: 'shows',
  USERS: 'users',
})

const activeScope = ref(SCOPE_VALUE.ALL)
const isUserScope = ref(false)
const pageTitle = ref('Discover')

let debounceTimer = null
function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(doSearch, 400)
}

async function doSearch() {
  if (!query.value.trim()) {
    results.value = []
    userResults.value = []
    return
  }

  loading.value = true
  try {
    if (isUserScope.value) {
      if (query.value.trim().length < 3) {
        userResults.value = []
        return
      }
      userResults.value = await authAPI.searchUsers(query.value.trim())
      results.value = []
      return
    }

    const data = await mediaAPI.search(query.value, activeFilter.value)
    if (data) {
      const type = activeFilter.value
      const typedRows = (data.results || [])
        .filter((row) => {
          if (type === 'multi') {
            return row.media_type === MEDIA_TYPE.MOVIE || row.media_type === MEDIA_TYPE.TV
          }
          return true
        })
        .map((row) => ({
          ...row,
          media_type: type === 'multi' ? (row.media_type || MEDIA_TYPE.MOVIE) : type,
        }))
      results.value = typedRows
      userResults.value = []
    }
  } finally {
    loading.value = false
  }
}

function mapScopeToFilter(scope) {
  if (scope === SCOPE_VALUE.MOVIES) return MEDIA_TYPE.MOVIE
  if (scope === SCOPE_VALUE.SHOWS) return MEDIA_TYPE.TV
  return 'multi'
}

function mapFilterToScope(value) {
  if (value === MEDIA_TYPE.MOVIE) return SCOPE_VALUE.MOVIES
  if (value === MEDIA_TYPE.TV) return SCOPE_VALUE.SHOWS
  if (value === 'users') return SCOPE_VALUE.USERS
  return SCOPE_VALUE.ALL
}

function applyScope(scope) {
  activeScope.value = scope
  isUserScope.value = scope === SCOPE_VALUE.USERS
  activeFilter.value = isUserScope.value ? 'multi' : mapScopeToFilter(scope)
}

function syncPageTitle() {
  pageTitle.value = query.value.trim() ? 'Search' : 'Discover'
}

function setScope(scope) {
  applyScope(scope)
  if (query.value.trim()) {
    doSearch()
  } else {
    results.value = []
    userResults.value = []
  }
  router.replace({
    name: 'search',
    query: buildSearchQuery(scope, query.value),
  })
}

function onSearchSubmit({ query: nextQuery, scope }) {
  applyScope(scope)
  router.replace({
    name: 'search',
    query: buildSearchQuery(scope, nextQuery),
  })
  query.value = nextQuery
  syncPageTitle()
  if (nextQuery) {
    doSearch()
  } else {
    results.value = []
    userResults.value = []
  }
}

function buildSearchQuery(scope, rawQuery) {
  const scopedValue = scope === SCOPE_VALUE.USERS ? 'users' : mapScopeToFilter(scope)
  const trimmedQuery = String(rawQuery || '').trim()
  return trimmedQuery ? { q: trimmedQuery, scope: scopedValue } : { scope: scopedValue }
}

onMounted(async () => {
  const initialScope = mapFilterToScope(route.query.scope || route.query.type || 'all')
  const initialQuery = String(route.query.q || '').trim()
  applyScope(initialScope)
  query.value = initialQuery
  syncPageTitle()

  if (query.value) {
    doSearch()
  }

  try {
    const [moviesData, tvData] = await Promise.all([
      mediaAPI.trending(MEDIA_TYPE.MOVIE),
      mediaAPI.trending(MEDIA_TYPE.TV),
    ])
    trendingMovies.value = moviesData?.results?.slice(0, 10) || []
    trendingTvShows.value = tvData?.results?.slice(0, 10) || []
  } finally {
    loadingDefault.value = false
  }
})

watch(
  () => route.query,
  (nextQuery) => {
    const nextScope = mapFilterToScope(nextQuery.scope || nextQuery.type || 'all')
    const nextValue = String(nextQuery.q || '').trim()
    const scopeChanged = activeScope.value !== nextScope
    applyScope(nextScope)
    if (query.value !== nextValue || scopeChanged) {
      query.value = nextValue
      syncPageTitle()
      if (nextValue) {
        doSearch()
      } else {
        results.value = []
        userResults.value = []
      }
    } else {
      syncPageTitle()
    }
  }
)

</script>
