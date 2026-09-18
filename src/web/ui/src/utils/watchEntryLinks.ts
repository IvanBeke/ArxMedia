// Shared route builders for watch-history entries and episode links.
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import type { WatchEntry } from '@/types/api'

export function getMovieLink(tmdbId: number): string {
  return `/movies/${tmdbId}`
}

export function getShowLink(tmdbId: number): string {
  return `/tv/${tmdbId}`
}

export function getEpisodeLink(
  tmdbId: number,
  seasonNumber: number | null | undefined,
  episodeNumber: number | null | undefined,
): string {
  return `/tv/${tmdbId}/season/${seasonNumber}/episode/${episodeNumber}`
}

export function getWatchEntryLink(entry: WatchEntry): string {
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.MOVIE) return getMovieLink(entry.tmdb_id)
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.EPISODE) {
    return getEpisodeLink(entry.tmdb_id, entry.season_number, entry.episode_number)
  }
  return getShowLink(entry.tmdb_id)
}

export function getWatchEntryTitleLink(entry: WatchEntry): string {
  if (entry.media_type === WATCH_ENTRY_MEDIA_TYPE.MOVIE) return getMovieLink(entry.tmdb_id)
  return getShowLink(entry.tmdb_id)
}
