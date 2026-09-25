import { describe, expect, it } from 'vitest'
import { historyItemQuery, historyItemQueryFromRoute, historyItemRoute } from '@/utils/historyFilters'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'

describe('history item filters', () => {
  it('builds a scoped history query for an episode', () => {
    const filter = {
      media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
      tmdb_id: 1399,
      season_number: 0,
      episode_number: 3,
    }

    expect(historyItemQuery(filter)).toEqual({
      media_type: 'episode',
      tmdb_id: 1399,
      season_number: 0,
      episode_number: 3,
    })
    expect(historyItemRoute(filter)).toEqual({
      name: 'history',
      query: {
        media_type: 'episode',
        tmdb_id: '1399',
        season_number: '0',
        episode_number: '3',
      },
    })
  })

  it('picks the hidden item filters from a route query', () => {
    expect(historyItemQueryFromRoute({
      media_type: 'movie',
      tmdb_id: ['603', '604'],
      season_number: '0',
      episode_number: '',
      page: '2',
    })).toEqual({
      tmdb_id: '603',
      season_number: '0',
    })
  })
})
