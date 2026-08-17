import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    component: () => import('@/views/HomeView.vue'),
    name: 'home',
    meta: { requiresAuth: true }
  },
  {
    path: '/dashboard',
    component: () => import('@/views/DashboardView.vue'),
    name: 'dashboard',
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    component: () => import('@/views/LoginView.vue'),
    name: 'login',
    meta: { guest: true }
  },
  {
    path: '/register',
    component: () => import('@/views/RegisterView.vue'),
    name: 'register',
    meta: { guest: true }
  },
  {
    path: '/search',
    component: () => import('@/views/SearchView.vue'),
    name: 'search',
    meta: { requiresAuth: true }
  },
  {
    path: '/movies/:id',
    component: () => import('@/views/MovieDetailView.vue'),
    name: 'movie-detail',
    meta: { requiresAuth: true }
  },
  {
    path: '/tv/:id',
    component: () => import('@/views/TVDetailView.vue'),
    name: 'tv-detail',
    meta: { requiresAuth: true }
  },
  {
    path: '/tv/:id/season/:seasonNumber',
    component: () => import('@/views/SeasonDetailView.vue'),
    name: 'season-detail',
    meta: { requiresAuth: true }
  },
  {
    path: '/tv/:id/season/:seasonNumber/episode/:episodeNumber',
    component: () => import('@/views/EpisodeDetailView.vue'),
    name: 'episode-detail',
    meta: { requiresAuth: true }
  },
  {
    path: '/watchlist',
    component: () => import('@/views/WatchlistView.vue'),
    name: 'watchlist',
    meta: { requiresAuth: true }
  },
  {
    path: '/history',
    component: () => import('@/views/HistoryView.vue'),
    name: 'history',
    meta: { requiresAuth: true }
  },
  {
    path: '/profile/:username',
    component: () => import('@/views/ProfileView.vue'),
    name: 'profile'
  },
  {
    path: '/profile/:username/followers',
    component: () => import('@/views/ProfileFollowersView.vue'),
    name: 'profile-followers'
  },
  {
    path: '/profile/:username/following',
    component: () => import('@/views/ProfileFollowingView.vue'),
    name: 'profile-following'
  },
  {
    path: '/settings',
    component: () => import('@/views/SettingsView.vue'),
    name: 'settings',
    meta: { requiresAuth: true }
  },
  {
    path: '/calendar',
    component: () => import('@/views/CalendarView.vue'),
    name: 'calendar',
    meta: { requiresAuth: true }
  },
  {
    path: '/data',
    component: () => import('@/views/DataTransferView.vue'),
    name: 'data-transfer',
    meta: { requiresAuth: true }
  },
  {
    path: '/lists',
    component: () => import('@/views/ListsView.vue'),
    name: 'lists',
    meta: { requiresAuth: true }
  },
  {
    path: '/lists/:id',
    component: () => import('@/views/ListDetailView.vue'),
    name: 'list-detail',
    meta: { requiresAuth: true }
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  const hasToken = !!localStorage.getItem('access_token')

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    if (hasToken && !auth.user) {
      await auth.init()
    }
    if (!auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }

  if (to.name === 'home' && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
