<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div v-if="loading" class="space-y-4">
      <div class="h-16 w-16 skeleton rounded-full"></div>
      <div class="h-8 w-48 skeleton rounded-md"></div>
    </div>

    <template v-else-if="profile">
      <div class="flex items-start gap-5 mb-8">
        <div class="w-16 h-16 rounded-full bg-brand-500/20 border-2 border-brand-500/30 flex items-center justify-center text-brand-400 text-2xl font-medium">
          {{ profile.username[0].toUpperCase() }}
        </div>
        <div>
          <h1 class="font-display text-2xl text-primary font-semibold">{{ profile.username }}</h1>
          <p v-if="profile.bio" class="text-gray-400 text-sm mt-1">{{ profile.bio }}</p>
          <div class="flex gap-4 mt-2 text-sm text-gray-500">
            <span><strong class="text-primary">{{ profile.followers_count }}</strong> followers</span>
            <span><strong class="text-primary">{{ profile.following_count }}</strong> following</span>
          </div>
        </div>
        <div class="ml-auto" v-if="auth.user?.username !== profile.username && auth.isAuthenticated">
          <button @click="toggleFollow" class="btn-primary text-sm">{{ isFollowing ? 'Unfollow' : 'Follow' }}</button>
        </div>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="card p-4 text-center">
          <p class="text-3xl font-display text-brand-500">{{ profile.total_watched_movies }}</p>
          <p class="text-xs text-gray-500 mt-1">Movies</p>
        </div>
        <div class="card p-4 text-center">
          <p class="text-3xl font-display text-brand-500">{{ profile.total_watched_episodes }}</p>
          <p class="text-xs text-gray-500 mt-1">Episodes</p>
        </div>
      </div>

      <!-- User's Public Lists -->
      <div v-if="lists.length" class="mt-8">
        <h2 class="section-title mb-4">Public Lists</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <RouterLink
            v-for="list in lists"
            :key="list.id"
            :to="`/lists/${list.id}`"
            class="card p-4 hover:bg-surface-200/50 transition-colors"
          >
            <h3 class="text-primary font-medium">{{ list.name }}</h3>
            <p class="text-gray-500 text-sm mt-1">{{ list.description || 'No description' }}</p>
            <p class="text-gray-600 text-xs mt-2">{{ list.item_count }} items</p>
          </RouterLink>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { authAPI, trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const profile = ref(null)
const loading = ref(true)
const isFollowing = ref(false)
const lists = ref([])

onMounted(async () => {
  try {
    const data = await authAPI.getUser(route.params.username)
    if (data) profile.value = data
  } finally {
    loading.value = false
  }

  try {
    const data = await trackingAPI.getLists()
    if (data) {
      lists.value = data.results || data
    }
  } catch (error) {
    console.error('Failed to load lists:', error)
  }
})

async function toggleFollow() {
  const data = await authAPI.follow(route.params.username)
  if (data) isFollowing.value = data.following
}
</script>
