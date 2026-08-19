<template>
  <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-6 sm:py-8 overflow-x-hidden">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <h1 class="font-display text-2xl text-primary font-semibold mb-6">{{ title }}</h1>

    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

    <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <div v-for="n in 15" :key="n" class="aspect-[2/3] rounded-md skeleton"></div>
    </div>

    <div v-else-if="items.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      <MediaCard
        v-for="item in items"
        :key="item.id"
        :item="item"
        :media-type="mediaType"
        :watched="isWatchedStatus(item)"
        :status="item.user_status?.status || 'none'"
        :show-quick-action="auth.isAuthenticated && canToggleWatchlist(item)"
        :quick-action-active="item.user_status?.status === 'plan_to_watch'"
        :quick-action-loading="isLoading(mediaType, item.id)"
        :quick-action-pulsing="isPulsing(mediaType, item.id)"
        :quick-action-aria-label="getWatchlistAriaLabel(item)"
        :show-watched-quick-action="auth.isAuthenticated"
        :watched-quick-action-loading="isWatchedLoading(mediaType, item.id)"
        :watched-quick-action-pulsing="isWatchedPulsing(mediaType, item.id)"
        :watched-quick-action-aria-label="t('tracking_mark_as_watched')"
        :remove-watched-quick-action-aria-label="t('tracking_mark_as_watched')"
        :remove-watched-quick-action-confirm-text="getRemoveHistoryConfirmText(item.media_type || mediaType)"
        @quick-action-watchlist="handleQuickAction(item)"
        @quick-action-watch-option="handleWatchOption(item, $event)"
        @quick-action-remove-watched="handleRemoveWatched(item)"
      />
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-8">
      <button @click="page--; load()" :disabled="page <= 1" class="btn-ghost text-sm px-3 py-1.5 rounded-md" :class="{ 'opacity-50': page <= 1 }">
        Prev
      </button>
      <span class="text-gray-400 text-xs sm:text-sm">Page {{ page }} of {{ totalPages }}</span>
      <button @click="page++; load()" :disabled="page >= totalPages" class="btn-ghost text-sm px-3 py-1.5 rounded-md" :class="{ 'opacity-50': page >= totalPages }">
        Next
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { mediaAPI } from '@/api'
import MediaCard from '@/components/MediaCard.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import { useAuthStore } from '@/stores/auth'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useWatchlistQuickActions } from '@/composables/useWatchlistQuickActions'
import { useWatchedQuickActions } from '@/composables/useWatchedQuickActions'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'
import { useI18n } from '@/i18n'

const props = defineProps({
  title: { type: String, required: true },
  mediaType: { type: String, required: true },
})

const items = ref([])
const loading = ref(true)
const page = ref(1)
const totalPages = ref(1)
const quickActionError = ref('')
const auth = useAuthStore()
const { t } = useI18n()

const {
  showDatePicker,
  pickerInitialValue,
  pickWatchedDateTime,
  handleDatePickerConfirm,
  handleDatePickerCancel,
} = useWatchedDateTimePicker()

const { resetTransientState, isLoading, isPulsing, toggleWatchlist } = useWatchlistQuickActions()
const {
  resetTransientState: resetWatchedTransientState,
  isLoading: isWatchedLoading,
  isPulsing: isWatchedPulsing,
  markWatched,
  unmarkWatched,
} = useWatchedQuickActions()

function canToggleWatchlist(item) {
  const status = item?.user_status?.status
  return status !== WATCH_ENTRY_STATUS.WATCHED && status !== WATCH_ENTRY_STATUS.WATCHING
}

function isWatchedStatus(item) {
  const status = item?.user_status?.status
  return status === WATCH_ENTRY_STATUS.WATCHED || status === WATCH_ENTRY_STATUS.WATCHING
}

function showQuickActionError(message) {
  quickActionError.value = message
  setTimeout(() => {
    quickActionError.value = ''
  }, 3500)
}

function getWatchlistAriaLabel(item) {
  const inWatchlist = item?.user_status?.status === 'plan_to_watch'
  if (props.mediaType === MEDIA_TYPE.TV) {
    return inWatchlist ? t('watchlist_remove_show') : t('watchlist_add_show')
  }
  return inWatchlist ? t('watchlist_remove_movie') : t('watchlist_add_movie')
}

function getRemoveHistoryConfirmText(mediaType) {
  if (mediaType === MEDIA_TYPE.TV) {
    return t('remove_history_confirm_show')
  }
  return t('remove_history_confirm_movie')
}

async function handleQuickAction(item) {
  try {
    if (!canToggleWatchlist(item)) {
      return
    }
    const inWatchlist = item?.user_status?.status === 'plan_to_watch'
    const result = await toggleWatchlist(props.mediaType, item.id, inWatchlist)
    item.user_status = {
      ...(item.user_status || {}),
      status: result === 'removed' ? 'none' : 'plan_to_watch',
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watchlist.'))
  }
}

async function handleWatchOption(item, option) {
  try {
    let watchedAt = null
    if (option === 'release') {
      const releaseDate = item.release_date || item.first_air_date
      watchedAt = releaseDate ? `${releaseDate}T00:00:00Z` : null
    } else if (option === 'date') {
      watchedAt = await pickWatchedDateTime(item?.user_status?.watched_at || '')
      if (!watchedAt) {
        return
      }
    }

    const nextStatus = await markWatched(props.mediaType, item.id, watchedAt)
    if (!nextStatus) {
      return
    }

    const nowIso = watchedAt || new Date().toISOString()
    item.user_status = {
      ...(item.user_status || {}),
      status: nextStatus,
      watched_at: nowIso,
      status_changed_at: nowIso,
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watched status.'))
  }
}

async function handleRemoveWatched(item) {
  try {
    const removed = await unmarkWatched(props.mediaType, item.id)
    if (!removed) {
      return
    }

    item.user_status = {
      ...(item.user_status || {}),
      status: WATCH_ENTRY_STATUS.NONE,
      watched_at: null,
      status_changed_at: null,
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watched status.'))
  }
}

async function load() {
  loading.value = true
  items.value = []
  try {
    const data = await mediaAPI.popular(props.mediaType, page.value)
    if (data) {
      items.value = data.results || []
      totalPages.value = data.total_pages || 1
    }
  } catch (error) {
    console.error('Failed to load popular media:', error)
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)

watch(
  () => auth.isAuthenticated,
  async (isAuthenticated) => {
    if (!isAuthenticated) {
      resetTransientState()
      resetWatchedTransientState()
      return
    }
  },
  { immediate: true }
)
</script>
