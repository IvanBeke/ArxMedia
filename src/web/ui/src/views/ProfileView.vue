<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div v-if="loading" class="space-y-4">
      <div class="h-16 w-16 skeleton rounded-full"></div>
      <div class="h-8 w-48 skeleton rounded-md"></div>
      <div class="h-28 skeleton rounded-lg"></div>
    </div>

    <template v-else-if="profile">
      <div class="flex items-start gap-5 mb-6">
        <div class="w-16 h-16 rounded-full bg-brand-500/20 border-2 border-brand-500/30 flex items-center justify-center text-brand-400 text-2xl font-medium">
          {{ profile.username[0].toUpperCase() }}
        </div>
        <div>
          <h1 class="font-display text-2xl text-primary font-semibold">{{ profile.username }}</h1>
          <p v-if="profile.bio" class="text-gray-400 text-sm mt-1">{{ profile.bio }}</p>
          <div class="flex flex-wrap gap-2 mt-2 text-xs text-gray-500">
            <RouterLink
              :to="`/profile/${profile.username}/followers`"
              class="inline-flex items-center gap-1.5 rounded-full border border-surface-200 px-2.5 py-1 hover:border-brand-500/40 hover:bg-brand-500/10 hover:text-primary transition-colors"
            >
              <strong class="text-primary">{{ profile.followers_count }}</strong>
              <span>{{ t('profile_followers_count_label') }}</span>
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </RouterLink>
            <RouterLink
              :to="`/profile/${profile.username}/following`"
              class="inline-flex items-center gap-1.5 rounded-full border border-surface-200 px-2.5 py-1 hover:border-brand-500/40 hover:bg-brand-500/10 hover:text-primary transition-colors"
            >
              <strong class="text-primary">{{ profile.following_count }}</strong>
              <span>{{ t('profile_following_count_label') }}</span>
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
            </RouterLink>
            <span class="badge bg-surface-200 text-secondary text-[10px]">{{ visibilityLabel }}</span>
            <span v-if="profile.viewer_relationship?.follows_you" class="badge bg-surface-200 text-secondary text-[10px]">{{ t('profile_badge_follows_you') }}</span>
            <span v-if="profile.viewer_relationship?.is_friend && !profile.viewer_relationship?.is_self" class="badge bg-brand-500/20 text-brand-400 text-[10px]">{{ t('profile_badge_friend') }}</span>
          </div>
        </div>
        <div class="ml-auto" v-if="!profile.viewer_relationship?.is_self && auth.isAuthenticated">
          <button @click="toggleFollow" class="btn-primary text-sm" :disabled="followLoading">{{ isFollowing ? 'Unfollow' : 'Follow' }}</button>
        </div>
      </div>

      <div class="card p-4 md:p-5 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <p class="text-[11px] uppercase tracking-wide text-muted">{{ t('profile_about_joined') }}</p>
            <p class="text-secondary mt-1">{{ formatDateByLocale(profile.created_at) }}</p>
          </div>
          <div>
            <p class="text-[11px] uppercase tracking-wide text-muted">{{ t('profile_about_location') }}</p>
            <p class="text-secondary mt-1">{{ profile.location || '-' }}</p>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
        <div class="card p-4 text-center">
          <p class="text-3xl font-display text-brand-500">{{ profile.total_watched_movies }}</p>
          <p class="text-xs text-gray-500 mt-1">Movies</p>
        </div>
        <div class="card p-4 text-center">
          <p class="text-3xl font-display text-brand-500">{{ profile.total_watched_episodes }}</p>
          <p class="text-xs text-gray-500 mt-1">Episodes</p>
        </div>
        <div class="card p-4 text-center">
          <p class="text-3xl font-display text-brand-500">{{ profile.stats?.ratings_count ?? '-' }}</p>
          <p class="text-xs text-gray-500 mt-1">Ratings</p>
        </div>
        <div class="card p-4 text-center">
          <p class="text-3xl font-display text-brand-500">{{ profile.stats?.watchlist_count ?? '-' }}</p>
          <p class="text-xs text-gray-500 mt-1">Watchlist</p>
        </div>
        <div class="card p-4 text-center">
          <p class="text-3xl font-display text-brand-500">{{ profile.stats?.average_rating ?? '-' }}</p>
          <p class="text-xs text-gray-500 mt-1">Avg Rating</p>
        </div>
      </div>

      <div class="mt-8 border-b border-surface-200">
        <nav class="flex gap-6">
          <button @click="activeTab = 'activity'" class="pb-3 text-sm font-medium" :class="activeTab === 'activity' ? 'tab-active' : 'tab-inactive'">{{ t('profile_tab_activity') }}</button>
          <button @click="activeTab = 'lists'" class="pb-3 text-sm font-medium" :class="activeTab === 'lists' ? 'tab-active' : 'tab-inactive'">{{ t('profile_tab_lists') }}</button>
        </nav>
      </div>

      <div class="mt-6">
        <template v-if="!canViewContent">
          <div class="card p-6">
            <h3 class="text-primary font-medium">{{ t('profile_locked_title') }}</h3>
            <p class="text-sm text-muted mt-2">{{ lockedMessage }}</p>
          </div>
        </template>

        <template v-else-if="activeTab === 'activity'">
          <div v-if="profile.recent_activity?.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            <div v-for="entry in profile.recent_activity" :key="entry.id" class="group relative">
              <HistoryMediaCard
                :entry="entry"
                :link-to="getEntryLink(entry)"
              />
            </div>
          </div>
          <div v-else class="card p-6 text-sm text-muted">{{ t('profile_empty_activity') }}</div>
        </template>

        <template v-else-if="activeTab === 'lists'">
          <div v-if="profile.visible_lists?.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <RouterLink
              v-for="list in profile.visible_lists"
              :key="list.id"
              :to="`/lists/${list.id}`"
              class="card p-4 hover:bg-surface-200/50 transition-colors"
            >
              <h3 class="text-primary font-medium">{{ list.name }}</h3>
              <p class="text-gray-500 text-sm mt-1">{{ list.description || 'No description' }}</p>
              <p class="text-gray-600 text-xs mt-2">{{ list.item_count }} items</p>
            </RouterLink>
          </div>
          <div v-else class="card p-6 text-sm text-muted">{{ t('profile_empty_lists') }}</div>
        </template>

      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { authAPI } from '@/api'
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { useAuthStore } from '@/stores/auth'
import { formatDateByLocale, useI18n } from '@/i18n'

const route = useRoute()
const auth = useAuthStore()
const { t } = useI18n()
const profile = ref(null)
const loading = ref(true)
const followLoading = ref(false)
const activeTab = ref('activity')

const isFollowing = computed(() => !!profile.value?.viewer_relationship?.is_following)
const canViewContent = computed(() => {
  const permissions = profile.value?.permissions
  return !!(permissions?.can_view_activity || permissions?.can_view_lists)
})
const visibilityLabel = computed(() => {
  const visibility = profile.value?.account_visibility
  if (visibility === 'private') return t('profile_visibility_private')
  if (visibility === 'friends_only') return t('profile_visibility_friends_only')
  return t('profile_visibility_public')
})
const lockedMessage = computed(() => {
  const visibility = profile.value?.account_visibility
  if (visibility === 'private') return t('profile_locked_private')
  if (visibility === 'friends_only') return t('profile_locked_description')
  return t('profile_locked_description')
})

async function loadProfile() {
  loading.value = true
  try {
    profile.value = await authAPI.getUser(route.params.username)
  } finally {
    loading.value = false
  }
}

function getEntryLink(entry) {
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.MOVIE) return `/movies/${entry.tmdb_id}`
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return `/tv/${entry.tmdb_id}/season/${entry.season_number}/episode/${entry.episode_number}`
  }
  return `/tv/${entry.tmdb_id}`
}

async function toggleFollow() {
  if (!auth.isAuthenticated || followLoading.value) return
  followLoading.value = true
  try {
    const data = await authAPI.follow(route.params.username)
    if (profile.value?.viewer_relationship) {
      profile.value.viewer_relationship.is_following = !!data.following
      profile.value.viewer_relationship.is_friend = !!data.is_friend
    }
    if (profile.value) {
      profile.value.followers_count = data.followers_count
      profile.value.following_count = profile.value.following_count
    }
    await loadProfile()
  } finally {
    followLoading.value = false
  }
}

watch(
  () => route.params.username,
  async () => {
    activeTab.value = 'activity'
    await loadProfile()
  },
  { immediate: true }
)
</script>
