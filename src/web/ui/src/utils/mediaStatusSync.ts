import type { MediaResult, MediaType } from '@/types/api'
import type { WatchEntryStatus } from '@/types/tracking'

export interface MediaStatusChangedPayload {
  tmdb_id: number | undefined
  media_type: MediaType
  status: WatchEntryStatus
  watched_at: string | null
  status_changed_at: string | null
}

export type StatusSyncItem = Pick<MediaResult, 'id'> &
  Partial<Pick<MediaResult, 'media_type' | 'release_date' | 'user_status'>> & { tmdb_id?: number | string | null }

function resolveEntryId(item: StatusSyncItem): number | string | undefined {
  if (item.tmdb_id !== undefined && item.tmdb_id !== null) return item.tmdb_id
  return item.id
}

function matchesEntry(item: StatusSyncItem, payload: MediaStatusChangedPayload): boolean {
  const entryId = resolveEntryId(item)
  if (entryId === undefined || payload.tmdb_id === undefined) return false
  if (Number(entryId) !== Number(payload.tmdb_id)) return false
  if (item.media_type && item.media_type !== payload.media_type) return false
  return true
}

/** Patch the matching entry's `user_status` in place. Returns true when an entry was updated. */
export function applyStatusChanged<T extends StatusSyncItem>(items: T[], payload: MediaStatusChangedPayload): boolean {
  const entry = items.find((item) => matchesEntry(item, payload))
  if (!entry) return false
  entry.user_status = {
    ...(entry.user_status ?? {}),
    status: payload.status,
    watched_at: payload.watched_at,
    status_changed_at: payload.status_changed_at,
  }
  return true
}

function releaseTime(value: unknown): number {
  if (typeof value !== 'string' || !value) return Number.POSITIVE_INFINITY
  const time = Date.parse(value)
  return Number.isFinite(time) ? time : Number.POSITIVE_INFINITY
}

/** Chronological (ascending) sort by release date; missing/invalid dates go last, stable. */
export function sortMediaByReleaseDate<T extends Pick<MediaResult, 'release_date'>>(items: T[]): T[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => releaseTime(a.item.release_date) - releaseTime(b.item.release_date) || a.index - b.index)
    .map(({ item }) => item)
}
