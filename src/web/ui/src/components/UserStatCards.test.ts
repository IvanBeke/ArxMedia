import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UserStatCards from '@/components/UserStatCards.vue'
import { libraryStats, ratingStats, watchCountStats, watchTimeStats } from '@/test-support/stats'

describe('UserStatCards', () => {
  const props = { watchCount: watchCountStats(), watchTime: watchTimeStats(), ratings: ratingStats(), library: libraryStats() }

  it('shows every card by default', () => {
    const wrapper = mount(UserStatCards, { props })

    expect(wrapper.findAll('.card p.text-2xl').map((value) => value.text())).toEqual(['12', '3', '40', '2', '2h 30m', '4', '3', '8'])
  })

  it('shows only the four headline cards without the library', () => {
    const wrapper = mount(UserStatCards, { props: { watchCount: props.watchCount, watchTime: props.watchTime, ratings: props.ratings } })

    expect(wrapper.findAll('.card p.text-xs').map((title) => title.text())).toEqual([
      'Movies Watched', 'Episodes Watched', 'Watch time', 'Avg. Rating',
    ])
  })

  it('shows a dash without an average rating', () => {
    const wrapper = mount(UserStatCards, { props: { ...props, ratings: ratingStats({ average_rating: null }) } })

    expect(wrapper.findAll('.card p.text-2xl').at(-1)?.text()).toBe('–')
  })
})
