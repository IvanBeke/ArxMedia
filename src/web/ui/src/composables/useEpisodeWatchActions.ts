import { trackingAPI } from '@/api'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'
import type { WatchedAtOption } from '@/utils/watchOptions'

interface EpisodeTarget { tmdbId: string | number; seasonNumber: string | number; episodeNumber: string | number }
interface EpisodeContext { pickerInitial?: string }
interface EpisodeWatchActionOptions { onError?: (message: string) => void }

export function useEpisodeWatchActions(options: EpisodeWatchActionOptions = {}) {
  const {
    onError = (message) => console.error(message),
  } = options

  const {
    showDatePicker,
    pickerInitialValue,
    pickWatchedDateTime,
    handleDatePickerConfirm,
    handleDatePickerCancel,
  } = useWatchedDateTimePicker()

  /** Returns the stored watch moment (null when unknown), or null when cancelled or failed. */
  async function markFromOption(option: WatchedAtOption | string, target: EpisodeTarget, context: EpisodeContext = {}): Promise<{ watchedAt: string | null } | null> {
    const resolution = await resolveWatchedAtFromOption(option, {
      pickDateTime: () => pickWatchedDateTime(context.pickerInitial || ''),
    })
    if (resolution.cancelled) {
      return null
    }

    try {
      const response = await trackingAPI.markEpisodeWatched({
        tmdb_id: target.tmdbId,
        season_number: target.seasonNumber,
        episode_number: target.episodeNumber,
        watched_at: resolution.watchedAt,
      })
      // The backend resolves tokens like "release_date"; use the moment it stored.
      return { watchedAt: response.watched_at }
    } catch (error) {
      onError(getApiErrorMessage(error, 'Could not mark episode as watched.'))
      return null
    }
  }

  async function unmark(target: EpisodeTarget): Promise<boolean> {
    try {
      await trackingAPI.unmarkEpisodeWatched({
        tmdb_id: target.tmdbId,
        season_number: target.seasonNumber,
        episode_number: target.episodeNumber,
      })
      return true
    } catch (error) {
      onError(getApiErrorMessage(error, 'Could not unmark this episode.'))
      return false
    }
  }

  return {
    showDatePicker,
    pickerInitialValue,
    pickWatchedDateTime,
    handleDatePickerConfirm,
    handleDatePickerCancel,
    markFromOption,
    unmark,
  }
}
