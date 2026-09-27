import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import ActivityHeatmap from '@/components/ActivityHeatmap.vue'
import type { ActivityDay, UserActivityHeatmap } from '@/types/api'

const { getUserActivity } = vi.hoisted(() => ({
  getUserActivity: vi.fn(),
}))

vi.mock('@/api', () => ({
  authAPI: { getUserActivity },
}))

function movieItem(overrides: Partial<ActivityDay['items'][number]> = {}): ActivityDay['items'][number] {
  return {
    media_type: 'movie',
    tmdb_id: 101,
    title: 'Heatmap Movie',
    release_year: 2020,
    ...overrides,
  }
}

function episodeItem(overrides: Partial<ActivityDay['items'][number]> = {}): ActivityDay['items'][number] {
  return {
    media_type: 'episode',
    tmdb_id: 202,
    title: 'Heatmap Show',
    season_number: 1,
    episode_number: 5,
    episode_code: 'S01E05',
    ...overrides,
  }
}

function day(date: string, items: ActivityDay['items']): ActivityDay {
  return { date, count: items.length, items }
}

// Wednesday 2026-09-16 through Friday 2026-09-18.
function heatmapPayload(): UserActivityHeatmap {
  return {
    days: [
      day('2026-09-16', [movieItem()]),
      day('2026-09-17', [episodeItem()]),
      day('2026-09-18', []),
    ],
    total: 2,
  }
}

function mountHeatmap(username = 'testuser') {
  return mount(ActivityHeatmap, {
    props: { username },
    global: {
      plugins: [createPinia()],
      stubs: { RouterLink: RouterLinkStub },
    },
  })
}

// DOM order: [0] day-label column, [1] month labels, [2] day cells.
function dayLabelColumn(wrapper: ReturnType<typeof mountHeatmap>) {
  return wrapper.findAll('.grid')[0]!
}

function dayGrid(wrapper: ReturnType<typeof mountHeatmap>) {
  return wrapper.findAll('.grid')[2]!
}

function cellWrappers(wrapper: ReturnType<typeof mountHeatmap>) {
  return dayGrid(wrapper).findAll(':scope > div')
}

describe('ActivityHeatmap', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getUserActivity.mockResolvedValue(heatmapPayload())
  })

  it('shows a skeleton while loading', () => {
    const promise = new Promise(() => {})
    getUserActivity.mockReturnValue(promise)
    const wrapper = mountHeatmap()

    expect(wrapper.find('.skeleton').exists()).toBe(true)
  })

  it('shows an error state with retry on failure', async () => {
    getUserActivity.mockRejectedValue(new Error('boom'))
    const wrapper = mountHeatmap()
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load activity.')

    getUserActivity.mockResolvedValue(heatmapPayload())
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Failed to load activity.')
    expect(wrapper.text()).toContain('2 items in the past year')
  })

  it('renders a Monday-start grid with padding cells before the first day', async () => {
    const wrapper = mountHeatmap()
    await flushPromises()

    // Wednesday start → 2 padding cells (Mon, Tue) + 3 days.
    const wrappers = cellWrappers(wrapper)
    expect(wrappers).toHaveLength(5)
    expect(wrappers[0]!.find('div').exists()).toBe(false)
    expect(wrappers[1]!.find('div').exists()).toBe(false)
    expect(wrappers[2]!.find('div').exists()).toBe(true)
  })

  it('colors cells by daily count', async () => {
    const wrapper = mountHeatmap()
    await flushPromises()

    const wrappers = cellWrappers(wrapper)
    expect(wrappers[2]!.find('div')!.classes()).toContain('bg-brand-500/25')
    expect(wrappers[3]!.find('div')!.classes()).toContain('bg-brand-500/25')
    expect(wrappers[4]!.find('div')!.classes()).toContain('bg-surface-200')
  })

  it('renders month labels above the grid', async () => {
    const wrapper = mountHeatmap()
    await flushPromises()

    const labels = wrapper.findAll('.grid')[1]!
    expect(labels.text()).toContain('Sep')
  })

  it('renders Mon/Wed/Fri labels down the left side', async () => {
    const wrapper = mountHeatmap()
    await flushPromises()

    const labels = dayLabelColumn(wrapper).findAll(':scope > span')
    expect(labels).toHaveLength(7)
    expect(labels.map((label) => label.text())).toEqual(['Mon', '', 'Wed', '', 'Fri', '', 'Sun'])
  })

  it('shows a popup with the day date and watched items on hover', async () => {
    const wrapper = mountHeatmap()
    await flushPromises()

    const firstCell = cellWrappers(wrapper)[2]!.find('div')!
    await firstCell.trigger('mouseenter')

    expect(document.body.textContent).toContain('September 16, 2026')
    expect(document.body.textContent).toContain('Heatmap Movie (2020)')

    // The popup survives the short trip from the cell, then hides after a delay.
    await firstCell.trigger('mouseleave')
    expect(document.body.textContent).toContain('Heatmap Movie (2020)')

    await new Promise((resolve) => setTimeout(resolve, 150))
    expect(document.body.textContent).not.toContain('Heatmap Movie (2020)')
  })

  it('labels episodes with the show name and episode code', async () => {
    const wrapper = mountHeatmap()
    await flushPromises()

    const secondCell = cellWrappers(wrapper)[3]!.find('div')!
    await secondCell.trigger('mouseenter')

    expect(document.body.textContent).toContain('Heatmap Show S01E05')
  })

  it('shows an empty popup message for days without activity', async () => {
    const wrapper = mountHeatmap()
    await flushPromises()

    const thirdCell = cellWrappers(wrapper)[4]!.find('div')!
    await thirdCell.trigger('mouseenter')

    expect(document.body.textContent).toContain('Nothing watched this day.')
  })

  it('shows an empty-state note when there is no activity', async () => {
    getUserActivity.mockResolvedValue({ days: [day('2026-09-16', [])], total: 0 })
    const wrapper = mountHeatmap()
    await flushPromises()

    expect(wrapper.text()).toContain('No activity in the past year.')
  })

  it('reloads when the username prop changes', async () => {
    const wrapper = mountHeatmap('user_one')
    await flushPromises()
    expect(getUserActivity).toHaveBeenCalledWith('user_one')

    await wrapper.setProps({ username: 'user_two' })
    await flushPromises()
    expect(getUserActivity).toHaveBeenCalledWith('user_two')
  })
})
