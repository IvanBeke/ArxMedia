<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-8">
      <RouterLink :to="`/profile/${route.params.username}`" class="text-muted text-sm hover:text-brand-400 transition inline-flex items-center gap-1 mb-3">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        {{ t('profile_back_to_profile') }}
      </RouterLink>
      <div class="flex flex-wrap items-end justify-between gap-3">
        <h1 class="font-display text-2xl text-primary font-semibold">{{ title }}</h1>
        <div class="text-xs text-muted">
          {{ t('profile_social_results', { count: count }) }}
        </div>
      </div>
    </div>

    <div v-if="loading" class="space-y-2">
      <div v-for="n in 6" :key="`followers-skeleton-${n}`" class="h-16 skeleton rounded-md"></div>
    </div>

    <template v-else>
      <div v-if="forbidden" class="card p-6 text-sm text-muted">{{ t('profile_locked_followers') }}</div>
      <div v-else-if="followers.length" class="space-y-3">
        <div v-for="user in followers" :key="`follower-${user.id}`" class="card p-4 md:p-5 flex items-center justify-between gap-4 hover:bg-surface-200/40 transition-colors">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-10 h-10 rounded-full bg-brand-500/20 border border-brand-500/30 text-brand-300 text-sm font-semibold flex items-center justify-center flex-shrink-0">
              {{ user.username[0]?.toUpperCase() }}
            </div>
            <div class="min-w-0">
              <RouterLink :to="`/profile/${user.username}`" class="text-primary text-sm font-semibold hover:text-brand-400">{{ user.username }}</RouterLink>
              <p v-if="user.bio" class="text-xs text-muted mt-1 truncate">{{ user.bio }}</p>
            </div>
          </div>
          <div class="text-[11px] text-muted whitespace-nowrap text-right">
            <span class="text-primary font-semibold">{{ user.followers_count }}</span>
            <span class="ml-1">{{ t('profile_followers_count_label') }}</span>
          </div>
        </div>

        <div class="flex flex-col items-center gap-2 pt-2">
          <p class="text-xs text-muted">{{ t('profile_page_indicator', { page, total: totalPages }) }}</p>

          <PaginationControls
            :current-page="page"
            :total-pages="totalPages"
            :disabled="loading"
            @go="goToPage"
          />
        </div>
      </div>
      <div v-else class="card p-6 text-sm text-muted">{{ t('profile_empty_followers') }}</div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { authAPI } from '@/api'
import PaginationControls from '@/components/PaginationControls.vue'
import { useI18n } from '@/i18n'

const route = useRoute()
const { t } = useI18n()

const followers = ref([])
const loading = ref(true)
const forbidden = ref(false)
const page = ref(1)
const totalPages = ref(1)
const count = ref(0)
const PAGE_SIZE = 20

const title = computed(() => t('profile_followers_page_title', { username: route.params.username }))

function normalizePagination(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length }
  }
  return {
    results: data?.results || [],
    count: Number.isInteger(data?.count) ? data.count : 0,
  }
}

async function loadFollowers(nextPage = 1) {
  loading.value = true
  forbidden.value = false
  try {
    const data = await authAPI.getFollowers(route.params.username, { page: nextPage })
    const normalized = normalizePagination(data)
    followers.value = normalized.results
    count.value = normalized.count
    page.value = nextPage
    totalPages.value = Math.max(1, Math.ceil(normalized.count / PAGE_SIZE))
  } catch (error) {
    if (error?.status === 403) {
      forbidden.value = true
    }
    followers.value = []
    count.value = 0
    totalPages.value = 1
  } finally {
    loading.value = false
  }
}

function goToPage(nextPage) {
  if (!Number.isInteger(nextPage) || nextPage < 1 || nextPage > totalPages.value || nextPage === page.value || loading.value) {
    return
  }
  loadFollowers(nextPage)
}

watch(
  () => route.params.username,
  async () => {
    page.value = 1
    totalPages.value = 1
    count.value = 0
    followers.value = []
    await loadFollowers(1)
  },
  { immediate: true }
)
</script>
