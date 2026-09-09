import { trackingAPI } from '@/api'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'
import { getApiErrorMessage } from '@/utils/errors'
import { nowInstantIso } from '@/utils/temporal'
import { resolveWatchedAtFromOption } from '@/utils/watchOptions'
import type { WatchedAtOption } from '@/utils/watchOptions'

interface EpisodeTarget { tmdbId: string | number; seasonNumber: string | number; episodeNumber: string | number }
interface EpisodeContext { releaseDate?: string; pickerInitial?: string }
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

  async function markFromOption(option: WatchedAtOption | string, target: EpisodeTarget, context: EpisodeContext = {}): Promise<string | null> {
    const resolution = await resolveWatchedAtFromOption(option, {
      releaseDate: context.releaseDate || '',
      pickDateTime: () => pickWatchedDateTime(context.pickerInitial || ''),
    })
    if (resolution.cancelled) {
      return null
    }
    const watchedAt = resolution.watchedAt

    try {
      await trackingAPI.markEpisodeWatched({
        tmdb_id: target.tmdbId,
        season_number: target.seasonNumber,
        episode_number: target.episodeNumber,
        watched_at: watchedAt,
      })
      return watchedAt || nowInstantIso()
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
