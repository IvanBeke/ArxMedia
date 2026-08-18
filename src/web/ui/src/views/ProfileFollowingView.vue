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
      <div v-for="n in 6" :key="`following-skeleton-${n}`" class="h-16 skeleton rounded-md"></div>
    </div>

    <template v-else>
      <div v-if="forbidden" class="card p-6 text-sm text-muted">{{ t('profile_locked_following') }}</div>
      <div v-else-if="following.length" class="space-y-3">
        <UserList
          :users="following"
          :followers-label="t('profile_followers_count_label')"
          :following-label="t('profile_following_count_label')"
        />

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
      <div v-else class="card p-6 text-sm text-muted">{{ t('profile_empty_following') }}</div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { authAPI } from '@/api'
import PaginationControls from '@/components/PaginationControls.vue'
import UserList from '@/components/UserList.vue'
import { useI18n } from '@/i18n'

const route = useRoute()
const { t } = useI18n()

const following = ref([])
const loading = ref(true)
const forbidden = ref(false)
const page = ref(1)
const totalPages = ref(1)
const count = ref(0)
const PAGE_SIZE = 20

const title = computed(() => t('profile_following_page_title', { username: route.params.username }))

function normalizePagination(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length }
  }
  return {
    results: data?.results || [],
    count: Number.isInteger(data?.count) ? data.count : 0,
  }
}

async function loadFollowing(nextPage = 1) {
  loading.value = true
  forbidden.value = false
  try {
    const data = await authAPI.getFollowing(route.params.username, { page: nextPage })
    const normalized = normalizePagination(data)
    following.value = normalized.results
    count.value = normalized.count
    page.value = nextPage
    totalPages.value = Math.max(1, Math.ceil(normalized.count / PAGE_SIZE))
  } catch (error) {
    if (error?.status === 403) {
      forbidden.value = true
    }
    following.value = []
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
  loadFollowing(nextPage)
}

watch(
  () => route.params.username,
  async () => {
    page.value = 1
    totalPages.value = 1
    count.value = 0
    following.value = []
    await loadFollowing(1)
  },
  { immediate: true }
)
</script>
