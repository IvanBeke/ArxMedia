<template>
  <WatchedDateTimePicker
    :open="showDatePicker"
    :initial-value="pickerInitialValue"
    title="When did you watch this?"
    @confirm="handleDatePickerConfirm"
    @cancel="handleDatePickerCancel"
  />

  <MediaCardShell
    :poster-url="posterUrl"
    :poster-alt="title"
    :poster-link-to="linkTo"
    :poster-aria-label="`Open ${title}`"
    :title-link-to="linkTo"
    :title-text="title"
  >
    <template #overlay-right>
      <div v-if="card.status.visible || card.hasUserRating" class="absolute top-2 right-2 flex items-center gap-1.5">
        <CardUserRating v-if="card.hasUserRating" :value="card.userRating" size="xs" />
        <CardStatusBadge v-if="card.status.visible" :status="card.status.value" />
      </div>
    </template>

    <template #overlay-left>
      <div v-if="card.showMediaTypeBadge" class="absolute top-2 left-2">
        <CardMediaTypeBadge :media-type="card.mediaType" />
      </div>
    </template>

    <template #poster-overlay>
      <div class="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
    </template>

    <template #actions>
      <MediaCardActions :visible="showAnyAction">
        <CardActionWatchlistToggle
          v-if="showWatchlistAction"
          :active="isInWatchlist"
          :loading="isLoading(resolvedMediaType, actionId)"
          :pulsing="isPulsing(resolvedMediaType, actionId)"
          :aria-label="watchlistAriaLabel"
          @trigger="toggleWatchlistAction"
        />
        <CardActionRemoveHistoryEntry
          v-if="showRemoveWatchedQuickActionButton"
          :loading="isWatchedLoading(resolvedMediaType, actionId)"
          :aria-label="removeWatchedAriaLabel"
          @trigger="openRemoveHistoryDialog"
        />
        <CardActionWatchedMenu
          v-if="showWatchedQuickActionButton"
          :release-date="card.actions.watchedMenu.releaseDate"
          :loading="isWatchedLoading(resolvedMediaType, actionId)"
          :pulsing="isWatchedPulsing(resolvedMediaType, actionId)"
          :aria-label="watchedAriaLabel"
          @select="selectWatchOption"
        />
        <CardActionRemoveHistoryEntry
          v-if="showListRemoveActionButton"
          :loading="removingFromList"
          aria-label="Remove from list"
          @trigger="openRemoveFromListDialog"
        />
        <CardActionWatchlistToggle
          v-if="showListAddActionButton"
          :active="false"
          :loading="addingToList"
          :pulsing="false"
          aria-label="Add to list"
          @trigger="addToListAction"
        />
      </MediaCardActions>
    </template>

    <template #meta>
      <div class="mt-0.5 flex items-center gap-2 px-0.5">
        <p class="text-xs text-gray-500">
          <span>{{ card.releaseDate }}</span>
        </p>
        <CardProviderRating v-if="card.providerRating" :value="card.providerRating" size="xs" />
      </div>
    </template>
  </MediaCardShell>

  <ConfirmDialog
    ref="removeHistoryDialog"
    title="Remove from watched history?"
    :message="removeHistoryConfirmText"
    confirm-label="Remove"
    cancel-label="Keep history"
    @confirm="confirmRemoveHistory"
  />

  <ConfirmDialog
    ref="removeFromListDialog"
    title="Remove from this list?"
    message="This removes the item from this list only. It does not remove watch history or ratings."
    confirm-label="Remove"
    cancel-label="Keep item"
    loading-label="Removing..."
    :loading="removingFromList"
    @confirm="confirmRemoveFromList"
  />
</template>

<script setup>
import { computed, ref } from 'vue'
import { trackingAPI } from '@/api'
import MediaCardShell from '@/components/cards/MediaCardShell.vue'
import MediaCardActions from '@/components/cards/MediaCardActions.vue'
import CardActionWatchlistToggle from '@/components/cards/primitives/CardActionWatchlistToggle.vue'
import CardActionRemoveHistoryEntry from '@/components/cards/primitives/CardActionRemoveHistoryEntry.vue'
import CardActionWatchedMenu from '@/components/cards/primitives/CardActionWatchedMenu.vue'
import CardMediaTypeBadge from '@/components/cards/primitives/CardMediaTypeBadge.vue'
import CardProviderRating from '@/components/cards/primitives/CardProviderRating.vue'
import CardStatusBadge from '@/components/cards/primitives/CardStatusBadge.vue'
import CardUserRating from '@/components/cards/primitives/CardUserRating.vue'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useMediaCardModel } from '@/composables/useMediaCardModel'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useAuthStore } from '@/stores/auth'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import { useI18n } from '@/i18n'
import { getApiErrorMessage } from '@/utils/errors'

const props = defineProps({
  item: { type: Object, required: true },
  mediaType: { type: String, default: MEDIA_TYPE.MOVIE },
  hideWatchlistAction: { type: Boolean, default: false },
  hideWatchedAction: { type: Boolean, default: false },
  allowWatchedRemoval: { type: Boolean, default: true },
  showListRemoveAction: { type: Boolean, default: false },
  showListAddAction: { type: Boolean, default: false },
  listContextId: { type: [Number, String], default: null },
  watched: { type: Boolean, default: false },
  status: { type: String, default: WATCH_ENTRY_STATUS.NONE },
  removeWatchedQuickActionConfirmText: { type: String, default: '' },
})

const emit = defineEmits(['error', 'status-changed', 'watchlist-removed', 'list-item-removed', 'list-item-added'])
const auth = useAuthStore()
const { t } = useI18n()

function emitError(message) {
  emit('error', message)
}

const {
  showDatePicker,
  pickerInitialValue,
  handleDatePickerConfirm,
  handleDatePickerCancel,
  canToggleWatchlist,
  isWatchedStatus,
  getWatchlistAriaLabel,
  getActionId,
  isLoading,
  isPulsing,
  isWatchedLoading,
  isWatchedPulsing,
  handleQuickAction,
  handleWatchOption,
  handleRemoveWatched,
} = useMediaCardQuickActions({ onError: emitError })

const { model } = useMediaCardModel(
  'mixed',
  computed(() => props.item),
  computed(() => ({
    mediaType: props.mediaType,
    watched: props.watched || props.item?.user_status?.status === WATCH_ENTRY_STATUS.WATCHED || props.item?.user_status?.status === WATCH_ENTRY_STATUS.WATCHING,
    status: props.status !== WATCH_ENTRY_STATUS.NONE ? props.status : (props.item?.user_status?.status || WATCH_ENTRY_STATUS.NONE),
    showMediaTypeBadge: true,
    showQuickAction: false,
    showWatchedQuickAction: false,
  }))
)

const card = computed(() => model.value)
const title = computed(() => card.value.title)
const posterUrl = computed(() => card.value.posterUrl)
const linkTo = computed(() => card.value.titleLinkTo)
const resolvedMediaType = computed(() => props.mediaType || card.value.mediaType)
const actionId = computed(() => getActionId(props.item))
const isInWatchlist = computed(() => props.item?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH)
const interactiveEnabled = computed(() => auth.isAuthenticated)
const isWatchedOrWatching = computed(() => {
  return isWatchedStatus(props.item)
})
const showWatchlistAction = computed(() => {
  if (!interactiveEnabled.value || props.hideWatchlistAction) {
    return false
  }
  return canToggleWatchlist(props.item)
})
const showWatchedQuickActionButton = computed(() => {
  if (!interactiveEnabled.value || props.hideWatchedAction) {
    return false
  }
  return !isWatchedOrWatching.value
})
const showRemoveWatchedQuickActionButton = computed(() => {
  if (!interactiveEnabled.value || props.hideWatchedAction || !props.allowWatchedRemoval) {
    return false
  }
  return isWatchedOrWatching.value
})
const showListRemoveActionButton = computed(() => {
  return interactiveEnabled.value && props.showListRemoveAction && Boolean(props.listContextId) && Boolean(props.item?.id)
})
const showListAddActionButton = computed(() => {
  return interactiveEnabled.value && props.showListAddAction && Boolean(props.listContextId) && Boolean(props.item?.tmdb_id || props.item?.id)
})
const showAnyAction = computed(() => {
  return showWatchlistAction.value
    || showWatchedQuickActionButton.value
    || showRemoveWatchedQuickActionButton.value
    || showListRemoveActionButton.value
    || showListAddActionButton.value
})
const watchlistAriaLabel = computed(() => getWatchlistAriaLabel(resolvedMediaType.value, isInWatchlist.value))
const watchedAriaLabel = computed(() => t('tracking_mark_as_watched'))
const removeWatchedAriaLabel = computed(() => 'Remove from watched history')
const removeHistoryConfirmText = computed(() => {
  if (props.removeWatchedQuickActionConfirmText) {
    return props.removeWatchedQuickActionConfirmText
  }
  if (card.value.mediaType === MEDIA_TYPE.TV) {
    return 'This will remove all watched episodes for this show from your history. Ratings and list membership are not changed.'
  }
  return 'This will remove this movie from your watched history. Ratings and list membership are not changed.'
})

const removeHistoryDialog = ref(null)
const removeFromListDialog = ref(null)
const removingFromList = ref(false)
const addingToList = ref(false)

function openRemoveHistoryDialog() {
  removeHistoryDialog.value?.showModal()
}

function confirmRemoveHistory() {
  removeWatchedAction()
}

function openRemoveFromListDialog() {
  removeFromListDialog.value?.showModal()
}

function emitStatusChanged() {
  const status = props.item?.user_status || {}
  emit('status-changed', {
    tmdb_id: props.item?.tmdb_id || props.item?.id,
    media_type: resolvedMediaType.value,
    status: status.status || WATCH_ENTRY_STATUS.NONE,
    watched_at: status.watched_at || null,
    status_changed_at: status.status_changed_at || null,
  })
}

async function toggleWatchlistAction() {
  const result = await handleQuickAction(props.item, resolvedMediaType.value)
  if (!result) {
    return
  }
  emitStatusChanged()
  if (result === 'removed') {
    emit('watchlist-removed', {
      tmdb_id: props.item?.tmdb_id || props.item?.id,
      media_type: resolvedMediaType.value,
    })
  }
}

async function selectWatchOption(option) {
  const nextStatus = await handleWatchOption(props.item, resolvedMediaType.value, option)
  if (!nextStatus) {
    return
  }
  emitStatusChanged()
}

async function removeWatchedAction() {
  const removed = await handleRemoveWatched(props.item, resolvedMediaType.value)
  if (!removed) {
    return
  }
  emitStatusChanged()
}

async function confirmRemoveFromList() {
  if (removingFromList.value || !props.listContextId || !props.item?.id) {
    return
  }
  removingFromList.value = true
  try {
    await trackingAPI.removeFromList(props.listContextId, props.item.id)
    removeFromListDialog.value?.close()
    emit('list-item-removed', {
      list_id: Number(props.listContextId),
      item_id: props.item.id,
      tmdb_id: props.item?.tmdb_id || null,
      media_type: resolvedMediaType.value,
    })
  } catch (error) {
    emitError(getApiErrorMessage(error, 'Could not remove item from list.'))
  } finally {
    removingFromList.value = false
  }
}

async function addToListAction() {
  if (addingToList.value || !props.listContextId) {
    return
  }
  const tmdbId = Number(props.item?.tmdb_id || props.item?.id)
  if (!tmdbId) {
    emitError('Could not add item to list.')
    return
  }
  addingToList.value = true
  try {
    await trackingAPI.addToList(props.listContextId, {
      media_type: resolvedMediaType.value,
      tmdb_id: tmdbId,
    })
    emit('list-item-added', {
      list_id: Number(props.listContextId),
      tmdb_id: tmdbId,
      media_type: resolvedMediaType.value,
    })
  } catch (error) {
    emitError(getApiErrorMessage(error, 'Could not add item to list.'))
  } finally {
    addingToList.value = false
  }
}
</script>
