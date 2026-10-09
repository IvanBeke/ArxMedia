import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import EpisodeCodePill from '@/components/EpisodeCodePill.vue'

describe('EpisodeCodePill', () => {
  it('renders regular episodes as Sxx·Exx', () => {
    const wrapper = mount(EpisodeCodePill, { props: { seasonNumber: 2, episodeNumber: 5 } })

    expect(wrapper.text()).toBe('S02·E05')
  })

  it('renders specials as S00·Exx instead of the fallback', () => {
    const wrapper = mount(EpisodeCodePill, { props: { seasonNumber: 0, episodeNumber: 3 } })

    expect(wrapper.text()).toBe('S00·E03')
  })

  it('falls back for negative or non-integer numbers', () => {
    expect(mount(EpisodeCodePill, { props: { seasonNumber: -1, episodeNumber: 3 } }).text()).toBe('--')
    expect(mount(EpisodeCodePill, { props: { seasonNumber: 1, episodeNumber: 0 } }).text()).toBe('--')
    expect(mount(EpisodeCodePill, { props: {} }).text()).toBe('--')
  })
})
