<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="font-display text-2xl text-primary font-semibold mb-1">{{ t('dashboard_title') }}</h1>
    <p class="text-muted text-sm mb-8">{{ t('dashboard_welcome') }} <span class="text-brand-400">{{ auth.user?.username }}</span></p>

    <Transition name="fade">
      <div v-if="actionError" role="alert" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ actionError }}
      </div>
    </Transition>

    <!-- Up Next Row -->
    <div class="mb-8">
      <RouterLink to="/my-shows?status=watching&has_next_episode=1" class="section-title mb-4 inline-flex items-center gap-1.5 hover:text-brand-400 transition-colors">
        <span>{{ t('dashboard_up_next') }}</span>
        <ChevronRight class="w-4 h-4" aria-hidden="true" />
      </RouterLink>
      <div v-if="loadingUpNext" class="flex gap-4 overflow-x-auto pb-2">
        <div v-for="n in 3" :key="n" class="w-40 h-60 skeleton rounded-lg flex-shrink-0"></div>
      </div>
      <LoadError v-else-if="upNextError" :message="t('error_load_up_next')" @retry="loadDashboard" />
      <div v-else-if="upNext?.length" class="flex gap-4 overflow-x-auto pb-2">
        <div
          v-for="item in upNext"
          :key="item.tmdb_id"
          class="flex-shrink-0 w-[165px] md:w-[173px] xl:w-[189px]"
        >
          <FutureEpisodeCard
            :show-title="item.show_name"
            :episode-title="item.next_episode?.name || ''"
            :episode-type="item.next_episode?.episode_type || ''"
            :season-number="item.next_episode?.season_number || 0"
            :episode-number="item.next_episode?.episode_number || 0"
            :poster-url="item.poster_url"
            :poster-link-to="getEpisodeLink(item.tmdb_id, item.next_episode?.season_number, item.next_episode?.episode_number)"
            :title-link-to="getShowLink(item.tmdb_id)"
            :show-new-badge="item.is_new"
            :show-watch-action="true"
            :watch-loading="markingId === item.tmdb_id"
            :jellyfin-url="jellyfinUrls[item.tmdb_id]"
            :progress-percent="item.progress_percent"
            :episode-duration-minutes="item.next_episode?.runtime"
            :episodes-left="item.episodes_left"
            :runtime-left-minutes="item.runtime_left_minutes"
            :runtime-left-has-unknown="item.runtime_left_has_unknown"
            @watch="markNextEpisodeWatched(item)"
          />
        </div>
      </div>
      <div v-else class="card p-6 text-center">
        <p class="text-muted text-sm">{{ t('dashboard_empty_shows') }}</p>
      </div>
    </div>

    <!-- Upcoming Row -->
    <div class="mb-8">
      <RouterLink to="/calendar" class="section-title mb-4 inline-flex items-center gap-1.5 hover:text-brand-400 transition-colors">
        <span>{{ t('dashboard_upcoming') }}</span>
        <ChevronRight class="w-4 h-4" aria-hidden="true" />
      </RouterLink>
      <div v-if="loadingUpcoming" class="flex gap-4 overflow-x-auto pb-2">
        <div v-for="n in 3" :key="n" class="w-40 h-60 skeleton rounded-lg flex-shrink-0"></div>
      </div>
      <LoadError v-else-if="upcomingError" :message="t('error_load_upcoming')" @retry="loadDashboard" />
      <div v-else-if="upcoming?.length" class="flex gap-4 overflow-x-auto pb-2">
        <div
          v-for="item in upcoming"
          :key="`${item.tmdb_id}-${item.season_number}-${item.episode_number}`"
          class="flex-shrink-0 w-[165px] md:w-[173px] xl:w-[189px]"
        >
          <FutureEpisodeCard
            :show-title="item.show_name"
            :episode-title="item.name || ''"
            :episode-type="item.episode_type || ''"
            :season-number="item.season_number"
            :episode-number="item.episode_number"
            :poster-url="item.poster_url"
            :poster-link-to="getEpisodeLink(item.tmdb_id, item.season_number, item.episode_number)"
            :title-link-to="getShowLink(item.tmdb_id)"
            :meta-text="formatUpcomingDateTime(item.air_date)"
          />
        </div>
      </div>
      <div v-else class="card p-6 text-center">
        <p class="text-muted text-sm">{{ t('dashboard_no_upcoming') }}</p>
      </div>
    </div>

    <div class="mb-8">
      <RouterLink to="/history" class="section-title mb-4 inline-flex items-center gap-1.5 hover:text-brand-400 transition-colors">
        <span>{{ t('dashboard_recent_activity') }}</span>
        <ChevronRight class="w-4 h-4" aria-hidden="true" />
      </RouterLink>
      <div v-if="loadingActivity" class="space-y-2">
        <div v-for="n in 5" :key="n" class="h-14 skeleton rounded-lg"></div>
      </div>
      <LoadError v-else-if="activityError" :message="t('error_recent_activity_unavailable')" @retry="loadDashboard" />
      <div v-else-if="activity?.length" class="flex gap-4 overflow-x-auto pb-2">
        <HistoryMediaCard
          v-for="entry in activity"
          :key="entry.id"
          :entry="entry"
          :link-to="getWatchEntryLink(entry)"
          :title-link-to="getWatchEntryTitleLink(entry)"
          :show-remove-action="true"
          :remove-loading="deletingEntryId === entry.id"
          :remove-confirm-text="getRemoveHistoryConfirmText(entry)"
          class="flex-shrink-0 w-[165px] md:w-[173px] xl:w-[189px]"
          @action:history-remove="removeRecentEntry"
        />
      </div>
      <div v-else class="card p-8 text-center">
        <p class="text-muted text-sm mb-3">{{ t('dashboard_no_activity') }}</p>
        <RouterLink to="/search" class="btn-primary text-sm">{{ t('dashboard_discover') }}</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { trackingAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import LoadError from '@/components/LoadError.vue'
import FutureEpisodeCard from '@/components/FutureEpisodeCard.vue'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { useJellyfinUpNextLinks } from '@/composables/useJellyfinUpNextLinks'
import { useI18n } from '@/i18n'
import { getRemoveHistoryConfirmText, useHistoryDelete } from '@/composables/useHistoryDelete'
import { getApiErrorMessage } from '@/utils/errors'
import { getEpisodeLink, getShowLink, getWatchEntryLink, getWatchEntryTitleLink } from '@/utils/watchEntryLinks'
import type { UpNextItem, UpcomingItem } from '@/api'
import type { WatchEntry } from '@/types/api'
import { usePageTitle } from '@/composables/usePageTitle'
import { ChevronRight } from '@lucide/vue'

const auth = useAuthStore()
const activity = ref<WatchEntry[] | null>(null)
const { t } = useI18n()
usePageTitle(() => t('dashboard_title'))
const loadingActivity = ref(true)
const upNext = ref<UpNextItem[] | null>(null)
const loadingUpNext = ref(true)
const upcoming = ref<UpcomingItem[] | null>(null)
const loadingUpcoming = ref(true)
const activityError = ref(false)
const upNextError = ref(false)
const upcomingError = ref(false)
const { errorMsg: actionError, showError: showActionError } = useFlashMessages()
const markingId = ref<number | null>(null)
const { urls: jellyfinUrls, load: loadJellyfinLinks } = useJellyfinUpNextLinks()

const upcomingDateTimeFormatter = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

function formatUpcomingDateTime(value: string | null): string {
  if (!value) return ''
  return upcomingDateTimeFormatter.format(new Date(value)).replace(',', '')
}

async function refreshTrackingLists() {
  const [upNextRes, activityRes] = await Promise.all([
    trackingAPI.getUpNext(),
    trackingAPI.getActivity(),
  ])
  upNext.value = upNextRes
  activity.value = activityRes
  void loadJellyfinLinks(upNextRes)
}

async function markNextEpisodeWatched(item: UpNextItem) {
  if (!item.next_episode || markingId.value) return
  markingId.value = item.tmdb_id
  try {
    await trackingAPI.markEpisodeWatched({
      tmdb_id: item.tmdb_id,
      season_number: item.next_episode.season_number,
      episode_number: item.next_episode.episode_number
    })
    await refreshTrackingLists()
  } catch (error: unknown) {
    showActionError(getApiErrorMessage(error, t('error_mark_episode')))
  } finally {
    markingId.value = null
  }
}

const { deletingEntryId, deleteEntry: removeRecentEntry } = useHistoryDelete({
  onDeleted: () => refreshTrackingLists(),
  onError: showActionError,
})

async function loadDashboard() {
  loadingUpNext.value = loadingUpcoming.value = loadingActivity.value = true
  const [upNextRes, upcomingRes, activityRes] = await Promise.allSettled([
    trackingAPI.getUpNext(),
    trackingAPI.getUpcoming(),
    trackingAPI.getActivity(),
  ])

  upNextError.value = upNextRes.status === 'rejected'
  if (upNextRes.status === 'fulfilled') {
    upNext.value = upNextRes.value
    void loadJellyfinLinks(upNextRes.value)
  }
  loadingUpNext.value = false

  upcomingError.value = upcomingRes.status === 'rejected'
  if (upcomingRes.status === 'fulfilled') upcoming.value = upcomingRes.value
  loadingUpcoming.value = false

  activityError.value = activityRes.status === 'rejected'
  if (activityRes.status === 'fulfilled') activity.value = activityRes.value
  loadingActivity.value = false
}

onMounted(loadDashboard)
</script>
