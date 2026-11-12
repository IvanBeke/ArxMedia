<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <FlashToast :messages="[{ text: actionError, kind: 'error' }]" />
    <header class="mb-6">
      <h1 class="font-display text-2xl font-semibold text-primary">{{ t('notifications_title') }}</h1>
      <p class="text-sm text-muted mt-1">{{ t('notifications_subtitle') }}</p>
    </header>

    <div v-if="loading" class="space-y-3">
      <div v-for="n in 3" :key="n" class="skeleton h-30 sm:h-42 rounded-lg"></div>
    </div>
    <LoadError v-else-if="loadError" :message="t('notifications_load_error')" @retry="load()" />
    <ul v-else-if="items.length" class="divide-y divide-surface-200">
      <li v-for="item in items" :key="item.id" class="flex items-center gap-3 sm:gap-4 py-4">
        <span class="self-stretch w-1 shrink-0 rounded-full" :class="{ 'bg-brand-500': !item.read }">
          <span v-if="!item.read" class="sr-only">{{ t('notifications_unread') }}</span>
        </span>
        <RouterLink
          :to="itemPath(item)" :aria-label="itemTitle(item)"
          class="w-20 sm:w-28 aspect-[2/3] shrink-0 rounded-md overflow-hidden bg-surface-200 focus-visible:outline-2 focus-visible:outline-brand-500"
        >
          <img v-if="item.poster_url" :src="item.poster_url" alt="" loading="lazy" class="w-full h-full object-cover" />
        </RouterLink>
        <p class="flex-1 min-w-0 text-base text-primary break-words text-pretty">
          <RouterLink
            :to="itemPath(item)"
            class="text-brand-700 hover:text-brand-800 dark:text-brand-400 dark:hover:text-brand-300 underline underline-offset-2 decoration-current/40 hover:decoration-current transition-colors focus-visible:outline-2 focus-visible:outline-brand-500"
          >
            {{ itemTitle(item) }}
          </RouterLink>
          {{ t('notifications_released', { date: formatDateByLocale(item.release_date) }) }}
        </p>
        <div class="flex shrink-0 flex-col sm:flex-row gap-1">
          <button
            v-if="!item.read" type="button" class="notification-action text-brand-700 dark:text-brand-400 hover:bg-brand-500/10"
            :aria-label="t('notifications_mark_read')" :title="t('notifications_mark_read')"
            :disabled="busy" @click="mutate(item, 'read')"
          >
            <Check class="w-5 h-5" aria-hidden="true" />
          </button>
          <button
            type="button" class="notification-action text-red-400 hover:bg-red-500/10"
            :aria-label="t('notifications_delete')" :title="t('notifications_delete')"
            :disabled="busy" @click="mutate(item, 'delete')"
          >
            <Trash class="w-5 h-5" aria-hidden="true" />
          </button>
        </div>
      </li>
    </ul>
    <div v-else class="card px-6 py-12 text-center">
      <Bell class="w-10 h-10 mx-auto mb-4 text-muted" aria-hidden="true" />
      <h2 class="text-lg font-medium text-primary">{{ t('notifications_empty_title') }}</h2>
      <p class="text-sm text-muted mt-2">{{ t('notifications_empty_body') }}</p>
    </div>

    <PaginationControls
      v-if="!loadError" :count="count" :page="page"
      :loaded-count="items.length" :disabled="loading || busy"
      @go="load($event)"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Bell, Check, Trash } from '@lucide/vue'
import { notificationsAPI } from '@/api'
import FlashToast from '@/components/FlashToast.vue'
import LoadError from '@/components/LoadError.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'
import { usePageTitle } from '@/composables/usePageTitle'
import { formatDateByLocale, useI18n } from '@/i18n'
import { useNotificationsStore } from '@/stores/notifications'
import { MEDIA_TYPE } from '@/constants/tracking'
import type { ReleaseNotification } from '@/types/api'
import { getApiErrorMessage } from '@/utils/errors'
import { invalidPageRecovery } from '@/utils/pagination'
import { getMovieLink, getShowLink } from '@/utils/watchEntryLinks'

const { t } = useI18n()
const notifications = useNotificationsStore()
const latestRequest = useLatestRequest()
const { errorMsg: actionError, showError } = useFlashMessages()

const items = ref<ReleaseNotification[]>([])
const count = ref(0)
const page = ref(1)
const loading = ref(true)
const loadError = ref(false)
const busy = ref(false)
usePageTitle(() => t('notifications_title'))

// `quiet` refetches in the background: no skeleton, and a failure keeps the rows already shown.
async function load(target = page.value, { quiet = false } = {}): Promise<void> {
  const signal = latestRequest.next()
  page.value = target
  if (!quiet) {
    loading.value = true
    loadError.value = false
  }
  try {
    const result = await notificationsAPI.list(target, { signal })
    items.value = result.results
    count.value = result.count
  } catch (error) {
    if (isAbortError(error)) return
    const recoveryPage = invalidPageRecovery(error, target)
    if (recoveryPage !== null) return load(recoveryPage, { quiet })
    if (!quiet) loadError.value = true
  } finally {
    if (!signal.aborted) loading.value = false
  }
}

async function mutate(item: ReleaseNotification, action: 'read' | 'delete') {
  busy.value = true
  try {
    if (action === 'read') await notificationsAPI.markRead(item.id)
    else await notificationsAPI.delete(item.id)
  } catch (error) {
    showError(getApiErrorMessage(error, t('notifications_action_error')))
    return
  } finally {
    busy.value = false
  }
  if (!item.read) notifications.unreadCount = Math.max(0, notifications.unreadCount - 1)
  if (action === 'read') {
    item.read = true
  } else {
    items.value = items.value.filter((row) => row.id !== item.id)
    await load(page.value, { quiet: true })
  }
}

function itemTitle(item: ReleaseNotification) {
  const title = item.title || t('notifications_unknown_title')
  return (item.season_number ?? 0) > 1 ? t('notifications_season_title', { title, season: item.season_number }) : title
}

function itemPath(item: ReleaseNotification) {
  if (item.media_type === MEDIA_TYPE.MOVIE) return getMovieLink(item.tmdb_id)
  const show = getShowLink(item.tmdb_id)
  return (item.season_number ?? 0) > 1 ? `${show}/season/${item.season_number}` : show
}

onMounted(() => { void load(1) })
</script>

<style scoped>
@reference "../assets/main.css";

.notification-action {
  @apply flex items-center justify-center w-11 h-11 rounded-md transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-wait focus-visible:outline-2 focus-visible:outline-brand-500;
}
</style>
