import { useI18n } from '@/i18n'
import { MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { useWatchlistQuickActions } from '@/composables/useWatchlistQuickActions'
import { useWatchedQuickActions } from '@/composables/useWatchedQuickActions'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'
import { nowInstantIso } from '@/utils/temporal'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'
import type { MediaType, MediaUserStatus } from '@/types/api'
import type { WatchedAtOption } from '@/utils/watchOptions'
import type { WatchEntryStatus } from '@/types/tracking'

type MediaId = string | number
interface MediaItem { id?: MediaId; tmdb_id?: MediaId; media_type?: MediaType; release_date?: string | null; user_status?: Partial<MediaUserStatus> | null }
interface MediaCardQuickActionOptions { onError?: (message: string) => void; onWatchlistRemoved?: (payload: { item: MediaItem; mediaType: MediaType | null; tmdbId: MediaId | undefined }) => void }

export function useMediaCardQuickActions(options: MediaCardQuickActionOptions = {}) {
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

  function resolveMediaType(item: MediaItem, mediaTypeOverride: MediaType | null = null): MediaType | null {
    return mediaTypeOverride || item?.media_type || null
  }

  function getActionId(item: MediaItem): MediaId | undefined {
    return item?.tmdb_id || item?.id
  }

  function canToggleWatchlist(item: MediaItem) {
    const status = item?.user_status?.status
    return status !== WATCH_ENTRY_STATUS.WATCHED && status !== WATCH_ENTRY_STATUS.WATCHING
  }

  function isWatchedStatus(item: MediaItem) {
    const status = item?.user_status?.status
    return status === WATCH_ENTRY_STATUS.WATCHED || status === WATCH_ENTRY_STATUS.WATCHING
  }

  function getWatchlistAriaLabel(mediaType: MediaType | null, inWatchlist: boolean) {
    if (mediaType === MEDIA_TYPE.TV) {
      return inWatchlist ? t('watchlist_remove_show') : t('watchlist_add_show')
    }
    return inWatchlist ? t('watchlist_remove_movie') : t('watchlist_add_movie')
  }

  function patchUserStatus(item: MediaItem, patch: Partial<MediaUserStatus>) {
    item.user_status = {
      ...(item.user_status || {}),
      ...patch,
    }
  }

  async function handleQuickAction(item: MediaItem, mediaTypeOverride: MediaType | null = null): Promise<'removed' | 'added' | null> {
    try {
      if (!canToggleWatchlist(item)) {
        return null
      }
      const mediaType = resolveMediaType(item, mediaTypeOverride)
      const actionId = getActionId(item)
      const inWatchlist = item?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
      if (!mediaType || actionId === undefined) return null
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

  async function handleWatchOption(item: MediaItem, mediaTypeOverride: MediaType | null = null, option: WatchedAtOption | string = 'now'): Promise<WatchEntryStatus | null> {
    try {
      const mediaType = resolveMediaType(item, mediaTypeOverride)
      const actionId = getActionId(item)

      if (!mediaType || actionId === undefined) return null
      const resolution = await resolveWatchedAtFromOption(option, {
        releaseDate: item.release_date || '',
        pickDateTime: () => pickWatchedDateTime(item?.user_status?.watched_at || ''),
      })
      if (resolution.cancelled) {
        return null
      }
      const watchedAt = resolution.watchedAt

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

  async function handleRemoveWatched(item: MediaItem, mediaTypeOverride: MediaType | null = null): Promise<boolean> {
    try {
      const mediaType = resolveMediaType(item, mediaTypeOverride)
      const actionId = getActionId(item)
      if (!mediaType || actionId === undefined) return false
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
