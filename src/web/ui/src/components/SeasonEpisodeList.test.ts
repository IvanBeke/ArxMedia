import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import WatchCheckmarkMenu from '@/components/WatchCheckmarkMenu.vue'
import { required } from '@/test-support/assertions'
import type { Episode } from '@/types/api'

beforeEach(() => {
  setActivePinia(createPinia())
})

const episodes: Episode[] = [
  { id: 11, tmdb_id: 11, episode_number: 3, name: 'Third', overview: '', still_path: null, still_url: null, air_date: '2020-03-01', air_time: null, broadcast_start: null, runtime: null, vote_average: 0, vote_count: 0, episode_type: '', guest_stars: [], crew: [] },
  { id: 12, tmdb_id: 12, episode_number: 4, name: 'Fourth', overview: '', still_path: null, still_url: null, air_date: null, air_time: null, broadcast_start: null, runtime: null, vote_average: 0, vote_count: 0, episode_type: '', guest_stars: [], crew: [] },
]

function mountList() {
  return mount(SeasonEpisodeList, {
    props: {
      episodes,
      tmdbId: 37854,
      seasonNumber: 2,
      isEpisodeWatched: (episodeNumber) => episodeNumber === 4,
      getEpisodeWatchedAt: () => '',
    },
    global: {
      stubs: { RouterLink: true },
    },
  })
}

describe('SeasonEpisodeList', () => {
  it('forwards watch-option payloads with the episode number and air date', async () => {
    const wrapper = mountList()
    const menus = wrapper.findAllComponents(WatchCheckmarkMenu)
    expect(menus).toHaveLength(2)

    required(menus[0], 'First watch menu').vm.$emit('select', 'now')
    await nextTick()

    expect(required(required(wrapper.emitted('watch-option'), 'Watch option event')[0], 'Watch option payload')[0]).toEqual({
      episodeNumber: 3,
      option: 'now',
      releaseDate: '2020-03-01',
    })
  })

  it('forwards the broadcast timestamp when one is available', async () => {
    const wrapper = mount(SeasonEpisodeList, {
      props: {
        episodes: [{ ...episodes[0]!, broadcast_start: '2020-03-01T14:15:00Z' }],
        tmdbId: 37854,
        seasonNumber: 0,
        isEpisodeWatched: () => false,
        getEpisodeWatchedAt: () => '',
      },
      global: { stubs: { RouterLink: true } },
    })

    wrapper.findComponent(WatchCheckmarkMenu).vm.$emit('select', 'release')
    await nextTick()

    expect(required(required(wrapper.emitted('watch-option'), 'Watch option event')[0], 'Watch option payload')[0]).toEqual({
      episodeNumber: 3,
      option: 'release',
      releaseDate: '2020-03-01T14:15:00Z',
    })
  })

  it('marks watched episodes via the watched flag and forwards their unwatch event', async () => {
    const wrapper = mountList()
    const menus = wrapper.findAllComponents(WatchCheckmarkMenu)

    expect(required(menus[1], 'Second watch menu').props('watched')).toBe(true)

    required(menus[1], 'Second watch menu').vm.$emit('unwatch')
    await nextTick()

    expect(required(required(wrapper.emitted('unwatch'), 'Unwatch event')[0], 'Unwatch event payload')[0]).toEqual({ episodeNumber: 4 })
  })
})
