import type { RouteLocationRaw } from 'vue-router'
import type { QueryParams, WatchEntryMediaType } from '@/types/api'

export type HistoryItemFilter = {
  media_type: WatchEntryMediaType
  tmdb_id: string | number
  season_number?: string | number
  episode_number?: string | number
}

export const HISTORY_ITEM_FILTER_KEYS = ['tmdb_id', 'season_number', 'episode_number'] as const

export function historyItemQuery(filter: HistoryItemFilter): QueryParams {
  const query: QueryParams = {
    media_type: filter.media_type,
    tmdb_id: filter.tmdb_id,
  }

  if (filter.season_number !== undefined) {
    query.season_number = filter.season_number
  }
  if (filter.episode_number !== undefined) {
    query.episode_number = filter.episode_number
  }

  return query
}

export function historyItemRoute(filter: HistoryItemFilter): RouteLocationRaw {
  const query = Object.fromEntries(
    Object.entries(historyItemQuery(filter)).map(([key, value]) => [key, String(value)]),
  )
  return { name: 'history', query }
}

export function historyItemQueryFromRoute(query: Record<string, unknown>): QueryParams {
  const params: QueryParams = {}

  for (const key of HISTORY_ITEM_FILTER_KEYS) {
    const rawValue = query[key]
    const value = Array.isArray(rawValue) ? rawValue[0] : rawValue
    if (typeof value === 'string' && value.length > 0) {
      params[key] = value
    }
  }

  return params
}
