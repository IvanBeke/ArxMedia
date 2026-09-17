import { createRouter, createWebHistory, type RouteLocationNormalized, type RouteLocationNormalizedLoaded, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authMeta = { requiresAuth: true }
const routes: RouteRecordRaw[] = [
  { path: '/', component: () => import('@/views/HomeView.vue'), name: 'home', meta: { guest: true } }, { path: '/dashboard', component: () => import('@/views/DashboardView.vue'), name: 'dashboard', meta: authMeta }, { path: '/my-shows', component: () => import('@/views/MyShowsView.vue'), name: 'my-shows', meta: authMeta }, { path: '/my-movies', component: () => import('@/views/MyMoviesView.vue'), name: 'my-movies', meta: authMeta }, { path: '/login', component: () => import('@/views/LoginView.vue'), name: 'login', meta: { guest: true } }, { path: '/register', component: () => import('@/views/RegisterView.vue'), name: 'register', meta: { guest: true } }, { path: '/search', component: () => import('@/views/SearchView.vue'), name: 'search', meta: authMeta }, { path: '/movies/:id', component: () => import('@/views/MovieDetailView.vue'), name: 'movie-detail', meta: authMeta }, { path: '/tv/:id', component: () => import('@/views/TVDetailView.vue'), name: 'tv-detail', meta: authMeta }, { path: '/tv/:id/season/:seasonNumber', component: () => import('@/views/SeasonDetailView.vue'), name: 'season-detail', meta: authMeta }, { path: '/tv/:id/season/:seasonNumber/episode/:episodeNumber', component: () => import('@/views/EpisodeDetailView.vue'), name: 'episode-detail', meta: authMeta }, { path: '/people/:id', component: () => import('@/views/PersonDetailView.vue'), name: 'person-detail', meta: authMeta }, { path: '/watchlist', component: () => import('@/views/WatchlistView.vue'), name: 'watchlist', meta: authMeta }, { path: '/history', component: () => import('@/views/HistoryView.vue'), name: 'history', meta: authMeta }, { path: '/profile/:username', component: () => import('@/views/ProfileView.vue'), name: 'profile', meta: authMeta }, { path: '/profile/:username/followers', component: () => import('@/views/ProfileFollowersView.vue'), name: 'profile-followers', meta: authMeta }, { path: '/profile/:username/following', component: () => import('@/views/ProfileFollowingView.vue'), name: 'profile-following', meta: authMeta }, { path: '/settings', component: () => import('@/views/SettingsView.vue'), name: 'settings', meta: authMeta }, { path: '/calendar', component: () => import('@/views/CalendarView.vue'), name: 'calendar', meta: authMeta }, { path: '/data', component: () => import('@/views/DataTransferView.vue'), name: 'data-transfer', meta: authMeta }, { path: '/lists', component: () => import('@/views/ListsView.vue'), name: 'lists', meta: authMeta }, { path: '/lists/:id', component: () => import('@/views/ListDetailView.vue'), name: 'list-detail', meta: authMeta }, { path: '/offline', component: () => import('@/views/OfflineView.vue'), name: 'offline' },
]
type ScrollPosition = { left?: number; top?: number; behavior?: ScrollBehavior } | false | void

function queriesEqualIgnoringTab(
  a: RouteLocationNormalized['query'],
  b: RouteLocationNormalizedLoaded['query'],
): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  keys.delete('tab')
  for (const key of keys) {
    if (String(a[key] ?? '') !== String(b[key] ?? '')) {
      return false
    }
  }
  return true
}

/**
 * Tab switches (same path, only `?tab=` changed) preserve scroll position;
 * every other navigation scrolls to top, except browser back/forward which
 * restores the saved position.
 */
export function resolveScrollPosition(
  to: RouteLocationNormalized,
  from: RouteLocationNormalizedLoaded,
  savedPosition: { left: number; top: number } | null,
): ScrollPosition {
  if (savedPosition) {
    return savedPosition
  }
  if (to.path === from.path && queriesEqualIgnoringTab(to.query, from.query)) {
    return
  }
  return { top: 0 }
}
const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: (to, from, savedPosition) => resolveScrollPosition(to, from, savedPosition) })
router.beforeEach(async (to) => { const auth = useAuthStore(); if (to.meta.requiresAuth && !auth.isAuthenticated) { if (localStorage.getItem('access_token') && !auth.user) await auth.init(); if (!auth.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } } } if (to.meta.guest && auth.isAuthenticated) return { name: 'dashboard' } })
export default router
