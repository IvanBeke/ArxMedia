import { describe, expect, it } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ProgressRow from '@/components/ProgressRow.vue'
import type { ShowProgressItem } from '@/types/api'

function planToWatchItem(): ShowProgressItem {
  return {
    tmdb_id: 4004,
    poster_url: '/delta.jpg',
    vote_average: 7.5,
    show_name: 'Delta Show',
    number_of_seasons: 1,
    status: 'plan_to_watch',
    provider_status: 'Returning Series',
    user_rating: null,
    genres: ['Drama'],
    networks: [],
    episode_runtime: 42,
    progress_percent: 0,
    watched_episodes: 0,
    total_episodes: 3,
    last_watched_at: null,
    started_at: null,
    episodes_left: 3,
    runtime_left_minutes: 126,
    runtime_left_has_unknown: false,
    next_episode: {
      season_number: 1,
      episode_number: 1,
      name: 'Delta Episode',
      still_url: null,
      air_date: '2026-01-01',
      episode_type: 'standard',
      vote_average: null,
      vote_count: null,
    },
    last_watched_episode: { season_number: null, episode_number: null },
  }
}

function mountRow(item: ShowProgressItem) {
  return mount(ProgressRow, {
    props: { item },
    global: {
      plugins: [createPinia()],
      stubs: { RouterLink: RouterLinkStub },
    },
  })
}

describe('ProgressRow plan-to-watch', () => {
  it('renders the plan-to-watch status pill', () => {
    const wrapper = mountRow(planToWatchItem())

    expect(wrapper.find('.status-pill').text()).toBe('Plan to watch')
  })

  it('renders the progress fraction and episodes left', () => {
    const wrapper = mountRow(planToWatchItem())

    expect(wrapper.text()).toContain('0/3 watched')
    expect(wrapper.text()).toContain('3 episodes left')
    expect(wrapper.text()).toContain('0%')
  })

  it('renders the next episode section', () => {
    const wrapper = mountRow(planToWatchItem())

    expect(wrapper.text()).toContain('Next episode')
    expect(wrapper.text()).toContain('Delta Episode')
  })

  it('hides the next episode section when there is no next episode', () => {
    const wrapper = mountRow({ ...planToWatchItem(), next_episode: null })

    expect(wrapper.text()).not.toContain('Next episode')
  })
})
