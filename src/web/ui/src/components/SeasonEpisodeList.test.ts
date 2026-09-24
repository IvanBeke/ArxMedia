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
  { id: 11, tmdb_id: 11, episode_number: 3, name: 'Third', overview: '', still_path: null, still_url: null, air_date: '2020-03-01', air_time: null, broadcast_start: null, runtime: null, vote_average: 0, vote_count: 0, episode_type: 'finale', guest_stars: [], crew: [] },
  { id: 12, tmdb_id: 12, episode_number: 4, name: 'Fourth', overview: '', still_path: null, still_url: null, air_date: null, air_time: null, broadcast_start: null, runtime: null, vote_average: 0, vote_count: 0, episode_type: 'standard', guest_stars: [], crew: [] },
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
  it('stacks episode content into two mobile rows and restores the row at md', () => {
    const wrapper = mountList()
    const rows = wrapper.findAll('.episode-row')

    expect(rows).toHaveLength(2)
    for (const row of rows) {
      expect(row.classes()).toEqual(expect.arrayContaining([
        'grid',
        'grid-cols-[auto_minmax(0,1fr)]',
        'md:flex',
      ]))
      expect(row.find('.episode-controls').classes()).toEqual(expect.arrayContaining([
        'flex-row',
        'md:flex-col',
      ]))
      expect(row.find('.episode-details').classes()).toEqual(expect.arrayContaining([
        'col-span-2',
        'md:col-auto',
        'md:flex-1',
      ]))
    }
  })

  it('keeps episode thumbnails at an adaptive 16:9 frame', () => {
    const wrapper = mountList()
    const thumbnails = wrapper.findAll('.episode-thumbnail')

    expect(thumbnails).toHaveLength(2)
    for (const thumbnail of thumbnails) {
      expect(thumbnail.classes()).toEqual(expect.arrayContaining([
        'self-start',
        'w-full',
        'max-w-64',
        'aspect-video',
        'md:max-w-none',
        'md:w-40',
        'md:flex-shrink-0',
      ]))
    }
  })

  it('overlays special episode types on thumbnails at every breakpoint', () => {
    const wrapper = mountList()
    const badges = wrapper.findAll('.episode-thumbnail .episode-type-pill')

    expect(badges).toHaveLength(1)
    expect(badges[0]?.text()).toBe('finale')
    expect(badges[0]?.classes()).toEqual(expect.arrayContaining([
      'pointer-events-none',
      'absolute',
      'top-2',
      'left-2',
    ]))
    expect(badges[0]?.classes()).not.toContain('hidden')
    expect(badges[0]?.classes()).not.toContain('md:hidden')
    expect(wrapper.find('.episode-meta .episode-type-pill').exists()).toBe(false)
  })

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
