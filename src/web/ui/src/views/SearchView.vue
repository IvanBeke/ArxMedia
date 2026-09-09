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
        :model-value="query"
        :scope="activeScope"
        :autofocus="true"
        :enable-preview="false"
        :inline-scope-selector="true"
        :submit-on-clear="true"
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

    <div v-else-if="results.length">
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <MediaCard
          v-for="item in results"
          :key="`${item.media_type}-${item.id}`"
          :item="item"
          :media-type="item.media_type || MEDIA_TYPE.MOVIE"
          @error="showQuickActionError"
        />
      </div>

      <PaginationControls
        v-if="totalPages > 1"
        :count="totalResults"
        :page="currentPage"
        :loaded-count="results.length"
        :max-visible-pages="10"
        :disabled="loading"
        @go="goToPage"
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
import PaginationControls from '@/components/PaginationControls.vue'
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
const currentPage = ref(1)
const totalPages = ref(1)
const totalResults = ref(0)
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

async function doSearch({ page = 1 } = {}) {
  const trimmedQuery = query.value.trim()
  if (!trimmedQuery) {
    results.value = []
    userResults.value = []
    totalResults.value = 0
    totalPages.value = 1
    currentPage.value = 1
    return
  }

  loading.value = true
  try {
    if (isUserScope.value) {
      if (trimmedQuery.length < 3) {
        userResults.value = []
        totalResults.value = 0
        totalPages.value = 1
        return
      }
      userResults.value = await authAPI.searchUsers(trimmedQuery)
      results.value = []
      return
    }

    const data = await mediaAPI.search(trimmedQuery, activeFilter.value, page)
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
      totalPages.value = Number.isFinite(data.total_pages) ? Math.max(1, data.total_pages) : 1
      totalResults.value = Number.isFinite(data.total_results) ? data.total_results : typedRows.length
      currentPage.value = Number.isFinite(data.page) ? Math.min(data.page, totalPages.value) : Math.min(page, totalPages.value)
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

function buildSearchQuery(scope, rawQuery, page = 1) {
  const scopedValue = scope === SCOPE_VALUE.USERS ? 'users' : mapScopeToFilter(scope)
  const trimmedQuery = String(rawQuery || '').trim()
  const searchQuery = {}

  if (trimmedQuery) {
    searchQuery.q = trimmedQuery
  }
  if (scope) {
    searchQuery.scope = scopedValue
  }
  if (trimmedQuery && page > 1) {
    searchQuery.page = String(page)
  }
  return searchQuery
}

function syncRouteFromState() {
  const nextQuery = buildSearchQuery(activeScope.value, query.value, currentPage.value)
  const currentScope = route.query.scope || route.query.type || 'all'
  const currentPageValue = String(route.query.page || '1')
  const currentSearchValue = String(route.query.q || '').trim()

  if (
    currentScope === (nextQuery.scope || 'all') &&
    currentSearchValue === (nextQuery.q || '') &&
    currentPageValue === String(nextQuery.page || '1')
  ) {
    return
  }

  router.push({ name: 'search', query: nextQuery })
}

function goToPage(page) {
  if (!query.value.trim()) return
  currentPage.value = page
  doSearch({ page })
  syncRouteFromState()
}

function setScope(scope) {
  const nextPage = 1
  applyScope(scope)
  currentPage.value = nextPage
  if (query.value.trim()) {
    doSearch({ page: nextPage })
  } else {
    results.value = []
    userResults.value = []
  }
  syncRouteFromState()
}

function onSearchSubmit({ query: nextQuery, scope }) {
  const nextPage = 1
  applyScope(scope)
  query.value = nextQuery
  currentPage.value = nextPage
  syncPageTitle()
  if (nextQuery) {
    doSearch({ page: nextPage })
  } else {
    results.value = []
    userResults.value = []
  }
  syncRouteFromState()
}

watch(
  () => route.query,
  async (nextQuery) => {
    const nextScope = mapFilterToScope(nextQuery.scope || nextQuery.type || 'all')
    const nextValue = String(nextQuery.q || '').trim()
    const nextPage = Number.parseInt(String(nextQuery.page || '1'), 10) || 1
    const scopeChanged = activeScope.value !== nextScope
    const pageChanged = currentPage.value !== nextPage
    const queryChanged = query.value.trim() !== nextValue

    if (!scopeChanged && !pageChanged && !queryChanged) {
      syncPageTitle()
      return
    }

    applyScope(nextScope)
    query.value = nextValue
    currentPage.value = nextPage
    syncPageTitle()

    if (nextValue) {
      await doSearch({ page: currentPage.value })
    } else {
      results.value = []
      userResults.value = []
      totalResults.value = 0
      totalPages.value = 1
      currentPage.value = 1
    }
  },
  { immediate: true }
)

onMounted(async () => {
  const initialScope = mapFilterToScope(route.query.scope || route.query.type || 'all')
  const initialQuery = String(route.query.q || '').trim()
  const initialPage = Number.parseInt(String(route.query.page || '1'), 10) || 1
  applyScope(initialScope)
  query.value = initialQuery
  currentPage.value = initialPage
  syncPageTitle()

  if (query.value) {
    await doSearch({ page: currentPage.value })
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
</script>
