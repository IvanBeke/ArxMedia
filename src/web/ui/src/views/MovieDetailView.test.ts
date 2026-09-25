import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import MovieDetailView from '@/views/MovieDetailView.vue'
import MediaHistoryTab from '@/components/MediaHistoryTab.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types/api'

const { getMovie, getMovieCredits, getMovieRecommendations, getCollection, getHistory, getRatings } = vi.hoisted(() => ({
  getMovie: vi.fn(),
  getMovieCredits: vi.fn(),
  getMovieRecommendations: vi.fn(),
  getCollection: vi.fn(),
  getHistory: vi.fn(),
  getRatings: vi.fn(),
}))

vi.mock('@/api', () => ({
  mediaAPI: {
    getMovie,
    getMovieCredits,
    getMovieRecommendations,
    getCollection,
  },
  trackingAPI: {
    getHistory,
    getRatings,
    dropMedia: vi.fn().mockResolvedValue({}),
    removeFromHistory: vi.fn().mockResolvedValue({}),
    rate: vi.fn().mockResolvedValue({}),
  },
}))

const TMDB_ID = 603
const TEST_USER: User = {
  id: 1,
  username: 'tester',
  email: '',
  bio: '',
  avatar: null,
  location: '',
  website: '',
  preferred_region: 'US',
  account_visibility: 'public',
  followers_count: 0,
  following_count: 0,
  total_watched_movies: 0,
  total_watched_episodes: 0,
  created_at: '',
}

const MediaHistoryTabStub = {
  props: { filter: { type: Object, required: true } },
  template: '<div class="history-tab-stub" />',
}

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/movies/:id', name: 'movie-detail', component: MovieDetailView },
      { path: '/history', name: 'history', component: { template: '<div />' } },
    ],
  })
  await router.push(`/movies/${TMDB_ID}?tab=history`)
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().user = TEST_USER

  const wrapper = mount(MovieDetailView, {
    global: {
      plugins: [router, pinia],
      stubs: {
        WatchedDateTimePicker: true,
        MovieUnwatchDialog: true,
        MediaActionsBar: true,
        WatchSplitButton: true,
        ActionGhostButton: true,
        AddToListPopover: true,
        StarRating: true,
        SpoilerBlock: true,
        RatingBadge: true,
        DetailHero: true,
        ExternalLinks: true,
        CastGrid: true,
        RecommendationsRow: true,
        CollectionStrip: true,
        MediaHistoryTab: MediaHistoryTabStub,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('MovieDetailView history tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getMovie.mockResolvedValue({
      id: TMDB_ID,
      media_type: MEDIA_TYPE.MOVIE,
      tmdb_id: TMDB_ID,
      title: 'The Matrix',
      overview: 'A hacker learns the truth.',
      genres: [],
      poster_url: null,
      backdrop_url: null,
      runtime: 136,
      language: 'en',
      tagline: '',
      status: 'Released',
      metadata_updated_at: '',
      collection: null,
      user_status: { status: 'watched' },
    })
    getMovieCredits.mockResolvedValue({ cast: [], crew: [], guest_stars: [] })
    getMovieRecommendations.mockResolvedValue({ results: [] })
    getCollection.mockResolvedValue(null)
    getHistory.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    getRatings.mockResolvedValue([])
  })

  it('renders a movie-scoped history tab', async () => {
    const wrapper = await mountView()
    const historyTab = wrapper.findAll('[role="tab"]').find((tab) => tab.text().includes('History'))

    expect(historyTab).toBeTruthy()
    expect(wrapper.findComponent(MediaHistoryTab).props('filter')).toEqual({
      media_type: 'movie',
      tmdb_id: String(TMDB_ID),
    })
  })
})
