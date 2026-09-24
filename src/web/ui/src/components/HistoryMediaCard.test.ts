import { describe, expect, it } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import HistoryMediaCard from '@/components/HistoryMediaCard.vue'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import type { WatchEntry } from '@/types/api'

function historyEntry(overrides: Partial<WatchEntry> = {}): WatchEntry {
  return {
    id: 1,
    media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
    tmdb_id: 100,
    watched_at: '2026-01-01T20:00:00Z',
    season_number: 1,
    episode_number: 2,
    created_at: '2026-01-01T20:00:00Z',
    title: 'The Finale',
    poster_path: null,
    poster_url: null,
    vote_average: 0,
    show_name: 'Example Show',
    episode_type: '',
    ...overrides,
  }
}

function mountCard(entry: WatchEntry) {
  return mount(HistoryMediaCard, {
    props: {
      entry,
      linkTo: '/tv/100/season/1/episode/2',
    },
    global: {
      stubs: { RouterLink: RouterLinkStub },
    },
  })
}

describe('HistoryMediaCard', () => {
  it('renders a special episode type beside the episode code', () => {
    const wrapper = mountCard(historyEntry({ episode_type: 'season_finale' }))
    const tag = wrapper.find('.episode-type-pill')

    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('season finale')
    expect(tag.classes()).toEqual(expect.arrayContaining(['shadow', 'ring-1']))
  })

  it.each([
    ['standard', { episode_type: 'standard' }],
    ['missing', { episode_type: '' }],
    ['movie', {
      media_type: WATCH_ENTRY_MEDIA_TYPE.MOVIE,
      season_number: null,
      episode_number: null,
      title: 'Example Movie',
      show_name: null,
      episode_type: '',
    }],
  ] satisfies Array<[string, Partial<WatchEntry>]>)('does not render a tag for %s entries', (_label, overrides) => {
    const wrapper = mountCard(historyEntry(overrides))

    expect(wrapper.find('.episode-type-pill').exists()).toBe(false)
  })
})
