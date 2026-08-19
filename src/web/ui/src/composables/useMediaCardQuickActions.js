import { useI18n } from '@/i18n'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useWatchlistQuickActions } from '@/composables/useWatchlistQuickActions'
import { useWatchedQuickActions } from '@/composables/useWatchedQuickActions'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'
import { nowInstantIso, plainDateToUserInstantIso } from '@/utils/temporal'

export function useMediaCardQuickActions(options = {}) {
  const {
    onError = () => {},
    onWatchlistRemoved = null,
  } = options

  const { t } = useI18n()

  const {
    showDatePicker,
    pickerInitialValue,
    pickWatchedDateTime,
    handleDatePickerConfirm,
    handleDatePickerCancel,
  } = useWatchedDateTimePicker()

  const {
    resetTransientState,
    isLoading,
    isPulsing,
    toggleWatchlist,
  } = useWatchlistQuickActions()

  const {
    resetTransientState: resetWatchedTransientState,
    isLoading: isWatchedLoading,
    isPulsing: isWatchedPulsing,
    markWatched,
    unmarkWatched,
  } = useWatchedQuickActions()

  function resolveMediaType(item, mediaTypeOverride = null) {
    return mediaTypeOverride || item?.media_type || null
  }

  function getActionId(item) {
    return item?.tmdb_id || item?.id
  }

  function canToggleWatchlist(item) {
    const status = item?.user_status?.status
    return status !== WATCH_ENTRY_STATUS.WATCHED && status !== WATCH_ENTRY_STATUS.WATCHING
  }

  function isWatchedStatus(item) {
    const status = item?.user_status?.status
    return status === WATCH_ENTRY_STATUS.WATCHED || status === WATCH_ENTRY_STATUS.WATCHING
  }

  function getWatchlistAriaLabel(mediaType, inWatchlist) {
    if (mediaType === MEDIA_TYPE.TV) {
      return inWatchlist ? t('watchlist_remove_show') : t('watchlist_add_show')
    }
    return inWatchlist ? t('watchlist_remove_movie') : t('watchlist_add_movie')
  }

  function patchUserStatus(item, patch) {
    item.user_status = {
      ...(item.user_status || {}),
      ...patch,
    }
  }

  async function handleQuickAction(item, mediaTypeOverride = null) {
    try {
      if (!canToggleWatchlist(item)) {
        return null
      }
      const mediaType = resolveMediaType(item, mediaTypeOverride)
      const actionId = getActionId(item)
      const inWatchlist = item?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
      const result = await toggleWatchlist(mediaType, actionId, inWatchlist)

      patchUserStatus(item, {
        status: result === 'removed' ? WATCH_ENTRY_STATUS.NONE : WATCH_ENTRY_STATUS.PLAN_TO_WATCH,
      })

      if (result === 'removed' && typeof onWatchlistRemoved === 'function') {
        onWatchlistRemoved({ item, mediaType, tmdbId: actionId })
      }

      return result
    } catch (error) {
      onError(getApiErrorMessage(error, 'Could not update watchlist.'))
      return null
    }
  }

  async function handleWatchOption(item, mediaTypeOverride = null, option = 'now') {
    try {
      const mediaType = resolveMediaType(item, mediaTypeOverride)
      const actionId = getActionId(item)
      let watchedAt = null

      if (option === 'release') {
        const releaseDate = item.release_date
        watchedAt = releaseDate ? plainDateToUserInstantIso(releaseDate) : null
      } else if (option === 'date') {
        watchedAt = await pickWatchedDateTime(item?.user_status?.watched_at || '')
        if (!watchedAt) {
          return null
        }
      }

      const nextStatus = await markWatched(mediaType, actionId, watchedAt)
      if (!nextStatus) {
        return null
      }

      const nowIso = watchedAt || nowInstantIso()
      patchUserStatus(item, {
        status: nextStatus,
        watched_at: nowIso,
        status_changed_at: nowIso,
      })

      return nextStatus
    } catch (error) {
      onError(getApiErrorMessage(error, 'Could not update watched status.'))
      return null
    }
  }

  async function handleRemoveWatched(item, mediaTypeOverride = null) {
    try {
      const mediaType = resolveMediaType(item, mediaTypeOverride)
      const actionId = getActionId(item)
      const removed = await unmarkWatched(mediaType, actionId)
      if (!removed) {
        return false
      }

      patchUserStatus(item, {
        status: WATCH_ENTRY_STATUS.NONE,
        watched_at: null,
        status_changed_at: null,
      })

      return true
    } catch (error) {
      onError(getApiErrorMessage(error, 'Could not update watched status.'))
      return false
    }
  }

  function resetAllTransientState() {
    resetTransientState()
    resetWatchedTransientState()
  }

  return {
    showDatePicker,
    pickerInitialValue,
    pickWatchedDateTime,
    handleDatePickerConfirm,
    handleDatePickerCancel,
    canToggleWatchlist,
    isWatchedStatus,
    getWatchlistAriaLabel,
    getActionId,
    resolveMediaType,
    isLoading,
    isPulsing,
    isWatchedLoading,
    isWatchedPulsing,
    handleQuickAction,
    handleWatchOption,
    handleRemoveWatched,
    resetAllTransientState,
  }
}
