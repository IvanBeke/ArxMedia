<template>
  <nav class="sticky top-0 z-50 bg-surface border-b border-surface-200 backdrop-blur-md">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-14">
        <!-- Logo -->
        <RouterLink to="/" class="flex items-center group">
          <img
            :src="'/static/branding/arxmedia/logo-full.svg'"
            alt="ArxMedia logo"
            class="hidden md:block h-10 w-auto"
          />
          <img
            :src="'/static/branding/arxmedia/logo-mark.svg'"
            alt="ArxMedia logo"
            class="md:hidden h-8 w-auto"
          />
        </RouterLink>

        <!-- Search bar -->
        <div class="flex flex-1 min-w-0 mx-2 md:mx-8 md:max-w-md">
          <SearchBar
            v-model="searchQuery"
            :scope="searchScope"
            compact
            placeholder="Search movies, series & anime, or #id"
            @update:scope="searchScope = $event"
            @submit="goSearch"
            @select-preview="goToPreviewItem"
          />
        </div>

        <!-- Desktop nav links -->
        <div class="hidden md:flex items-center gap-1">
          <template v-if="auth.isAuthenticated">
            <RouterLink to="/dashboard" class="nav-link">{{ t('nav_dashboard') }}</RouterLink>
            <RouterLink to="/search" class="nav-link hidden lg:block">{{ t('nav_discover') }}</RouterLink>
            <RouterLink to="/history" class="nav-link hidden lg:block">History</RouterLink>
            <RouterLink to="/lists" class="nav-link hidden lg:block">{{ t('nav_lists') }}</RouterLink>
            <RouterLink to="/calendar" class="nav-link hidden xl:block">{{ t('nav_calendar') }}</RouterLink>
          </template>

          <template v-else>
            <RouterLink to="/search" class="nav-link hidden lg:block">{{ t('nav_discover') }}</RouterLink>
            <RouterLink to="/login" class="btn-ghost text-sm px-3 py-1.5">Sign In</RouterLink>
            <RouterLink to="/register" class="btn-primary text-sm px-3 py-1.5 ml-1">Join</RouterLink>
          </template>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-1">
          <button
            ref="mobileMenuButtonRef"
            @click="showMobileMenu = !showMobileMenu"
            class="md:hidden p-2 rounded-md text-muted hover:text-primary hover:bg-surface-100 transition-colors"
            aria-label="Open navigation menu"
            aria-haspopup="menu"
            :aria-expanded="showMobileMenu ? 'true' : 'false'"
          >
            <svg v-if="!showMobileMenu" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <div v-if="auth.isAuthenticated" class="relative" ref="userMenuRef">
            <button
              @click="showUserMenu = !showUserMenu"
              class="flex items-center gap-1.5 p-1 rounded-md hover:bg-surface-100 transition-colors cursor-pointer"
              :aria-label="t('nav_open_user_menu')"
              aria-haspopup="menu"
              :aria-expanded="showUserMenu ? 'true' : 'false'"
            >
              <div class="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400 text-xs font-medium cursor-pointer">
                {{ auth.user?.username?.[0]?.toUpperCase() }}
              </div>
            </button>

            <Transition name="fade">
              <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 bg-surface border border-surface-200 rounded-lg shadow-xl py-1 z-[120]">
                <RouterLink :to="`/profile/${auth.user?.username}`" @click="showUserMenu = false" class="dropdown-item">
                  Profile
                </RouterLink>
                <RouterLink to="/watchlist" @click="showUserMenu = false" class="dropdown-item">Watchlist</RouterLink>
                <RouterLink to="/history" @click="showUserMenu = false" class="dropdown-item">History</RouterLink>
                <RouterLink to="/lists" @click="showUserMenu = false" class="dropdown-item">Lists</RouterLink>
                <RouterLink to="/calendar" @click="showUserMenu = false" class="dropdown-item">{{ t('nav_calendar') }}</RouterLink>
                <RouterLink to="/data" @click="showUserMenu = false" class="dropdown-item">{{ t('nav_data') }}</RouterLink>
                <RouterLink to="/settings" @click="showUserMenu = false" class="dropdown-item">{{ t('nav_settings') }}</RouterLink>
                <hr class="border-surface-200 my-1" />
                <button @click="logout" class="dropdown-item w-full text-left text-red-400 hover:text-red-300">Sign Out</button>
              </div>
            </Transition>
          </div>

          <!-- Theme Toggle -->
          <button @click="theme.toggle()" class="p-2 rounded-md hover:bg-surface-100 transition-colors text-muted hover:text-primary md:ml-2" :aria-label="t('nav_toggle_theme')">
            <svg v-if="theme.isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
            </svg>
          </button>
        </div>
      </div>

      <Transition name="fade">
        <div v-if="showMobileMenu" ref="mobileMenuRef" class="md:hidden py-2 border-t border-surface-200">
          <div class="flex flex-col gap-1 pb-1">
            <template v-if="auth.isAuthenticated">
              <RouterLink to="/dashboard" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_dashboard') }}</RouterLink>
              <RouterLink to="/search" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_discover') }}</RouterLink>
              <RouterLink to="/history" @click="showMobileMenu = false" class="mobile-nav-link">History</RouterLink>
              <RouterLink to="/lists" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_lists') }}</RouterLink>
              <RouterLink to="/calendar" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_calendar') }}</RouterLink>
              <RouterLink to="/data" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_data') }}</RouterLink>
              <RouterLink to="/settings" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_settings') }}</RouterLink>
              <RouterLink :to="`/profile/${auth.user?.username}`" @click="showMobileMenu = false" class="mobile-nav-link">Profile</RouterLink>
              <button @click="logout" class="mobile-nav-link text-left text-red-400 hover:text-red-300">Sign Out</button>
            </template>

            <template v-else>
              <RouterLink to="/search" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_discover') }}</RouterLink>
              <RouterLink to="/login" @click="showMobileMenu = false" class="mobile-nav-link">Sign In</RouterLink>
              <RouterLink to="/register" @click="showMobileMenu = false" class="mobile-nav-link">Join</RouterLink>
            </template>
          </div>
        </div>
      </Transition>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { onClickOutside } from '@vueuse/core'
import SearchBar from '@/components/SearchBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useI18n } from '@/i18n'
import { MEDIA_TYPE } from '@/constants/tracking'

const auth = useAuthStore()
const theme = useThemeStore()
const router = useRouter()
const searchQuery = ref('')
const searchScope = ref('all')
const showUserMenu = ref(false)
const showMobileMenu = ref(false)
const userMenuRef = ref(null)
const mobileMenuRef = ref(null)
const mobileMenuButtonRef = ref(null)
const { t } = useI18n()

onClickOutside(userMenuRef, () => { showUserMenu.value = false })
onClickOutside(mobileMenuRef, () => { showMobileMenu.value = false }, { ignore: [mobileMenuButtonRef] })

function scopeToQueryValue(scope) {
  if (scope === 'movies') return MEDIA_TYPE.MOVIE
  if (scope === 'shows') return MEDIA_TYPE.TV
  if (scope === 'users') return 'users'
  return 'all'
}

function goSearch({ query, scope }) {
  if (query) {
    router.push({ name: 'search', query: { q: query, scope: scopeToQueryValue(scope) } })
    searchQuery.value = ''
    searchScope.value = 'all'
  } else {
    router.push({ name: 'search' })
  }
}

function goToPreviewItem(item) {
  if (item.kind === 'user') {
    router.push(`/profile/${item.username}`)
    return
  }
  if (item.media_type === MEDIA_TYPE.TV) {
    router.push(`/tv/${item.id}`)
    return
  }
  router.push(`/movies/${item.id}`)
}

function logout() {
  auth.logout()
  showUserMenu.value = false
  showMobileMenu.value = false
  router.push('/')
}
</script>

<style scoped>
@reference "../assets/main.css";

.nav-link {
  @apply px-3 py-2 text-sm text-muted hover:text-primary transition-colors font-medium;
}
.dropdown-item {
  @apply block px-4 py-2 text-sm hover:text-primary hover:bg-surface-100 transition-colors text-secondary;
}

.mobile-nav-link {
  @apply px-2 py-2 text-sm text-secondary hover:text-primary hover:bg-surface-100 rounded-md transition-colors;
}
</style>
