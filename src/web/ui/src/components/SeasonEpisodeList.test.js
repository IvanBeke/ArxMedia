import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import SeasonEpisodeList from '@/components/SeasonEpisodeList.vue'
import WatchCheckmarkMenu from '@/components/WatchCheckmarkMenu.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

const episodes = [
  { id: 11, episode_number: 3, name: 'Third', air_date: '2020-03-01' },
  { id: 12, episode_number: 4, name: 'Fourth', air_date: null },
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

    menus[0].vm.$emit('select', 'now')
    await nextTick()

    expect(wrapper.emitted('watch-option')[0][0]).toEqual({
      episodeNumber: 3,
      option: 'now',
      releaseDate: '2020-03-01',
    })
  })

  it('marks watched episodes via the watched flag and forwards their unwatch event', async () => {
    const wrapper = mountList()
    const menus = wrapper.findAllComponents(WatchCheckmarkMenu)

    expect(menus[1].props('watched')).toBe(true)

    menus[1].vm.$emit('unwatch')
    await nextTick()

    expect(wrapper.emitted('unwatch')[0][0]).toEqual({ episodeNumber: 4 })
  })
})
