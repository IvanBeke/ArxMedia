import { describe, expect, it } from 'vitest'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import type { WatchEntry } from '@/types/api'
import {
  getEpisodeLink,
  getMovieLink,
  getShowLink,
  getWatchEntryLink,
  getWatchEntryTitleLink,
} from '@/utils/watchEntryLinks'

function entry(overrides: Partial<WatchEntry>): WatchEntry {
  return {
    id: 1,
    media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
    tmdb_id: 100,
    watched_at: '2026-01-01T00:00:00Z',
    season_number: 1,
    episode_number: 2,
    created_at: '2026-01-01T00:00:00Z',
    title: 'Episode',
    poster_path: null,
    poster_url: null,
    vote_average: 0,
    show_name: 'Show',
    episode_type: '',
    ...overrides,
  }
}

describe('watchEntryLinks', () => {
  it('builds base links', () => {
    expect(getMovieLink(10)).toBe('/movies/10')
    expect(getShowLink(20)).toBe('/tv/20')
    expect(getEpisodeLink(30, 1, 2)).toBe('/tv/30/season/1/episode/2')
  })

  it('links movie entries to the movie page', () => {
    const movie = entry({ media_type: WATCH_ENTRY_MEDIA_TYPE.MOVIE })
    expect(getWatchEntryLink(movie)).toBe('/movies/100')
    expect(getWatchEntryTitleLink(movie)).toBe('/movies/100')
  })

  it('links episode entries to the episode page with show title to the show', () => {
    const episode = entry({ media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE })
    expect(getWatchEntryLink(episode)).toBe('/tv/100/season/1/episode/2')
    expect(getWatchEntryTitleLink(episode)).toBe('/tv/100')
  })

  it('falls back to the show page for unknown entry types', () => {
    const unknown = entry({ media_type: 'tv' as WatchEntry['media_type'] })
    expect(getWatchEntryLink(unknown)).toBe('/tv/100')
    expect(getWatchEntryTitleLink(unknown)).toBe('/tv/100')
  })
})
