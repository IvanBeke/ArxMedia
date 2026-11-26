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

        <div v-if="auth.isAuthenticated" class="flex flex-1 min-w-0 mx-2 md:mx-8 md:max-w-md">
          <SearchBar
            v-model="searchQuery"
            :scope="searchScope"
            compact
            @update:scope="searchScope = $event"
            @submit="goSearch"
            @select-preview="goToPreviewItem"
          />
        </div>
        <div v-else class="flex-1"></div>

        <!-- Desktop nav links -->
        <div class="hidden lg:flex items-center gap-1">
          <template v-if="auth.isAuthenticated">
            <RouterLink to="/search" class="nav-link hidden lg:block">{{ t('nav_discover') }}</RouterLink>
            <div
              class="relative"
              @mouseenter="showLibraryMenu = true"
              @mouseleave="showLibraryMenu = false"
            >
              <button
                type="button"
                class="nav-link inline-flex items-center gap-1 cursor-pointer"
                aria-haspopup="true"
                :aria-expanded="showLibraryMenu ? 'true' : 'false'"
              >
                <span>{{ t('nav_library') }}</span>
                <ChevronDown class="w-3 h-3 transition-transform" :class="showLibraryMenu ? 'rotate-180' : ''" aria-hidden="true" />
              </button>
              <Transition name="fade">
                <div v-if="showLibraryMenu" class="absolute left-0 top-full w-40 bg-surface border border-surface-200 rounded-lg shadow-xl py-1 z-[120]">
                  <RouterLink to="/my-shows" @click="showLibraryMenu = false" class="dropdown-item">{{ t('page_my_shows') }}</RouterLink>
                  <RouterLink to="/my-movies" @click="showLibraryMenu = false" class="dropdown-item">{{ t('page_my_movies') }}</RouterLink>
                </div>
              </Transition>
            </div>
            <RouterLink to="/history" class="nav-link hidden lg:block">{{ t('history_title') }}</RouterLink>
            <RouterLink to="/watchlist" class="nav-link hidden lg:block">{{ t('page_watchlist') }}</RouterLink>
          </template>

          <template v-else>
            <RouterLink to="/login" class="btn-primary text-sm px-3 py-1.5">{{ t('nav_log_in') }}</RouterLink>
            <RouterLink to="/register" class="btn-ghost text-sm px-3 py-1.5 ml-1 bg-surface-100 border-surface-300 text-secondary hover:bg-surface-200 hover:text-primary">{{ t('nav_create_account') }}</RouterLink>
          </template>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-1">
          <button
            ref="mobileMenuButtonRef"
            @click="showMobileMenu = !showMobileMenu"
            class="lg:hidden p-2 rounded-md text-muted hover:text-primary hover:bg-surface-100 transition-colors"
            :aria-label="t('nav_open_menu')"
            aria-haspopup="menu"
            :aria-expanded="showMobileMenu ? 'true' : 'false'"
          >
            <Menu v-if="!showMobileMenu" class="w-5 h-5" />
            <X v-else class="w-5 h-5" />
          </button>

          <div v-if="auth.isAuthenticated" class="relative" ref="userMenuRef">
            <button
              @click="showUserMenu = !showUserMenu"
              class="flex items-center gap-1.5 p-1 rounded-md hover:bg-surface-100 transition-colors cursor-pointer"
              :aria-label="t('nav_open_user_menu')"
              aria-haspopup="menu"
              :aria-expanded="showUserMenu ? 'true' : 'false'"
            >
              <UserAvatar v-if="auth.user" :username="auth.user.username" :src="auth.user.avatar" size="sm" class="cursor-pointer" />
            </button>

            <Transition name="fade">
              <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 bg-surface border border-surface-200 rounded-lg shadow-xl py-1 z-[120]">
                <RouterLink :to="`/profile/${auth.user?.username}`" @click="showUserMenu = false" class="dropdown-item">
                  {{ t('nav_profile') }}
                </RouterLink>
                <RouterLink :to="`/profile/${auth.user?.username}/stats`" @click="showUserMenu = false" class="dropdown-item">{{ t('stats_title') }}</RouterLink>
                <RouterLink to="/lists" @click="showUserMenu = false" class="dropdown-item">{{ t('nav_lists') }}</RouterLink>
                <RouterLink to="/calendar" @click="showUserMenu = false" class="dropdown-item">{{ t('nav_calendar') }}</RouterLink>
                <RouterLink to="/data" @click="showUserMenu = false" class="dropdown-item">{{ t('nav_data') }}</RouterLink>
                <RouterLink to="/settings" @click="showUserMenu = false" class="dropdown-item">{{ t('nav_settings') }}</RouterLink>
                <a
                  v-if="auth.user?.is_staff"
                  href="/admin/"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="dropdown-item"
                  @click="showUserMenu = false"
                >
                  <span class="inline-flex items-center gap-2">
                    <ExternalLink class="w-4 h-4" aria-hidden="true" />
                    {{ t('nav_admin') }}
                  </span>
                </a>
                <hr class="border-surface-200 my-1" />
                <button @click="logout" class="dropdown-item w-full text-left text-red-400 hover:text-red-300">{{ t('nav_sign_out') }}</button>
              </div>
            </Transition>
          </div>

          <RouterLink
            v-if="auth.isAuthenticated"
            to="/notifications"
            class="p-2 rounded-md text-muted hover:text-primary hover:bg-surface-100 transition-colors focus-visible:outline-2 focus-visible:outline-brand-500"
            :aria-label="notifications.unreadCount ? t('notifications_nav_unread', { count: notifications.unreadCount }) : t('notifications_title')"
            :title="t('notifications_title')"
          >
            <BellDot v-if="notifications.unreadCount" class="w-5 h-5" aria-hidden="true" />
            <Bell v-else class="w-5 h-5" aria-hidden="true" />
          </RouterLink>

          <!-- Theme Toggle -->
          <button @click="theme.toggle()" class="p-2 rounded-md hover:bg-surface-100 transition-colors text-muted hover:text-primary md:ml-2" :aria-label="t('nav_toggle_theme')">
            <Sun v-if="theme.isDark" class="w-5 h-5" />
            <Moon v-else class="w-5 h-5" />
          </button>
        </div>
      </div>

      <Transition name="fade">
        <div v-if="showMobileMenu" ref="mobileMenuRef" class="lg:hidden py-2 border-t border-surface-200">
          <div class="flex flex-col gap-1 pb-1">
            <template v-if="auth.isAuthenticated">
              <RouterLink to="/search" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_discover') }}</RouterLink>
              <RouterLink to="/my-shows" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('page_my_shows') }}</RouterLink>
              <RouterLink to="/my-movies" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('page_my_movies') }}</RouterLink>
              <RouterLink to="/history" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('history_title') }}</RouterLink>
              <RouterLink to="/watchlist" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('page_watchlist') }}</RouterLink>
              <RouterLink to="/calendar" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_calendar') }}</RouterLink>
              <RouterLink to="/data" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_data') }}</RouterLink>
              <RouterLink to="/settings" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_settings') }}</RouterLink>
              <a
                v-if="auth.user?.is_staff"
                href="/admin/"
                target="_blank"
                rel="noopener noreferrer"
                class="mobile-nav-link inline-flex items-center gap-2"
                @click="showMobileMenu = false"
              >
                <ExternalLink class="w-4 h-4" aria-hidden="true" />
                {{ t('nav_admin') }}
              </a>
              <RouterLink :to="`/profile/${auth.user?.username}`" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_profile') }}</RouterLink>
              <RouterLink :to="`/profile/${auth.user?.username}/stats`" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('stats_title') }}</RouterLink>
              <button @click="logout" class="mobile-nav-link text-left text-red-400 hover:text-red-300">{{ t('nav_sign_out') }}</button>
            </template>

            <template v-else>
              <RouterLink to="/login" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_log_in') }}</RouterLink>
              <RouterLink to="/register" @click="showMobileMenu = false" class="mobile-nav-link">{{ t('nav_create_account') }}</RouterLink>
            </template>
          </div>
        </div>
      </Transition>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, BellDot, ChevronDown, ExternalLink, Menu, Moon, Sun, X } from '@lucide/vue'
import { onClickOutside } from '@vueuse/core'
import SearchBar from '@/components/SearchBar.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useNotificationsStore } from '@/stores/notifications'
import { useI18n } from '@/i18n'
import { MEDIA_TYPE } from '@/constants/tracking'
import type { PersonSearchResult, UserCard } from '@/types/api'

type SearchScope = 'all' | 'movies' | 'shows' | 'users' | 'people'
type SearchSubmission = { query: string; scope: SearchScope }
type SearchPreviewItem = (UserCard & { kind: 'user' }) | (PersonSearchResult & { kind: 'person' }) | { id: number; media_type: (typeof MEDIA_TYPE)[keyof typeof MEDIA_TYPE] }

const auth = useAuthStore()
const theme = useThemeStore()
const notifications = useNotificationsStore()
const router = useRouter()
const searchQuery = ref('')
const searchScope = ref<SearchScope>('all')
const showUserMenu = ref(false)
const showMobileMenu = ref(false)
const showLibraryMenu = ref(false)
const userMenuRef = ref<HTMLElement | null>(null)
const mobileMenuRef = ref<HTMLElement | null>(null)
const mobileMenuButtonRef = ref<HTMLButtonElement | null>(null)
const { t } = useI18n()

onClickOutside(userMenuRef, () => { showUserMenu.value = false })
onClickOutside(mobileMenuRef, () => { showMobileMenu.value = false }, { ignore: [mobileMenuButtonRef] })
watch(() => auth.user?.id, (userId) => { if (userId) void notifications.refreshUnread() }, { immediate: true })

function scopeToQueryValue(scope: SearchScope) {
  if (scope === 'movies') return MEDIA_TYPE.MOVIE
  if (scope === 'shows') return MEDIA_TYPE.TV
  if (scope === 'users') return 'users'
  if (scope === 'people') return 'people'
  return 'all'
}

function goSearch({ query, scope }: SearchSubmission) {
  if (query) {
    router.push({ name: 'search', query: { q: query, scope: scopeToQueryValue(scope) } })
    searchQuery.value = ''
    searchScope.value = 'all'
  } else {
    router.push({ name: 'search' })
  }
}

function goToPreviewItem(item: SearchPreviewItem) {
  if ('kind' in item) {
    if (item.kind === 'person') {
      router.push(`/people/${item.id}`)
      return
    }
    router.push(`/profile/${item.username}`)
    return
  }
  if (item.media_type === MEDIA_TYPE.TV) {
    router.push(`/tv/${item.id}`)
    return
  }
  router.push(`/movies/${item.id}`)
}

async function logout() {
  await auth.logout().catch(() => {})
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
