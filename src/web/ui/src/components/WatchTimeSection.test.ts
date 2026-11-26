import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import WatchTimeSection from '@/components/WatchTimeSection.vue'
import StatColumns from '@/components/StatColumns.vue'
import StatStackedBar from '@/components/StatStackedBar.vue'
import { usePreferencesStore } from '@/stores/preferences'
import { mockStatsAPI, monthlyStats, watchTimeStats, yearsStats } from '@/test-support/stats'
import type { WatchTimeStats } from '@/types/api'

const ALL_TIME = watchTimeStats({ movie_minutes: 43_788, episode_minutes: 258_333, watch_time_minutes: 302_121 })

let api: ReturnType<typeof mockStatsAPI>

function mountSection(allTime: Partial<{ data: WatchTimeStats | null; loading: boolean; error: boolean }> = {}) {
  const section = reactive({ data: ALL_TIME as WatchTimeStats | null, loading: false, error: false, load: vi.fn(), ...allTime })
  const wrapper = mount(WatchTimeSection, { props: { username: 'bob', allTime: section } })
  return { wrapper, section }
}

const button = (wrapper: ReturnType<typeof mountSection>['wrapper'], label: string) => wrapper.get(`button[aria-label="${label}"]`)
const visibleBars = (wrapper: ReturnType<typeof mountSection>['wrapper']) =>
  wrapper.findAllComponents(StatStackedBar).filter((bar) => !bar.element.closest('.invisible'))
const visibleChart = (wrapper: ReturnType<typeof mountSection>['wrapper']) =>
  wrapper.findAll('ul.items-end').find((chart) => !chart.element.closest('.invisible'))

describe('WatchTimeSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    api = mockStatsAPI()
    api.monthly.mockImplementation((_username, year) => Promise.resolve(monthlyStats({ year: year ?? 2026 })))
  })

  it('shows the all-time split and, below the year controls, the monthly chart of the current year', async () => {
    const { wrapper } = mountSection()
    await flushPromises()

    const bars = visibleBars(wrapper)
    expect(bars).toHaveLength(1)
    expect(wrapper.text()).toContain('All time')
    expect(bars[0]!.text()).toContain('30d 9h 48m')
    expect(wrapper.findAll('li[title]')).toHaveLength(12)
    expect(button(wrapper, 'Go to the current year').text()).toBe('2026')
    expect(api.monthly).toHaveBeenCalledWith('bob', 2026)
  })

  it('goes back and forth between years, within the first year with data and the current year', async () => {
    const { wrapper } = mountSection()
    await flushPromises()
    const prev = button(wrapper, 'Previous year')
    const next = button(wrapper, 'Next year')

    expect(prev.attributes('disabled')).toBeUndefined()
    expect(next.attributes('disabled')).toBeDefined()

    await prev.trigger('click')
    await flushPromises()
    expect(api.monthly).toHaveBeenLastCalledWith('bob', 2025)
    expect(button(wrapper, 'Go to the current year').text()).toBe('2025')
    expect(next.attributes('disabled')).toBeUndefined()

    await prev.trigger('click')
    await flushPromises()
    expect(button(wrapper, 'Go to the current year').text()).toBe('2024')
    expect(prev.attributes('disabled')).toBeDefined()

    await next.trigger('click')
    await flushPromises()
    expect(api.monthly).toHaveBeenLastCalledWith('bob', 2025)
  })

  it('returns to the current year from the year in the middle, which does nothing on the current year', async () => {
    const { wrapper } = mountSection()
    await flushPromises()
    const current = button(wrapper, 'Go to the current year')
    expect(current.attributes('disabled')).toBeDefined()

    await button(wrapper, 'Previous year').trigger('click')
    await flushPromises()
    expect(current.attributes('disabled')).toBeUndefined()

    await current.trigger('click')
    await flushPromises()

    expect(current.text()).toBe('2026')
    expect(api.monthly).toHaveBeenLastCalledWith('bob', 2026)
    expect(current.attributes('disabled')).toBeDefined()
  })

  it('cannot go back without any dated entry', async () => {
    api.years.mockResolvedValue(yearsStats({ earliest_year: null }))

    const { wrapper } = mountSection()
    await flushPromises()

    expect(button(wrapper, 'Previous year').attributes('disabled')).toBeDefined()
  })

  it('keeps the old chart visible and dimmed while another year loads, then animates it', async () => {
    const { wrapper } = mountSection()
    await flushPromises()
    let resolveYear: (value: ReturnType<typeof monthlyStats>) => void = () => {}
    api.monthly.mockReturnValueOnce(new Promise((resolve) => { resolveYear = resolve }))

    await button(wrapper, 'Previous year').trigger('click')

    expect(wrapper.find('.skeleton').exists()).toBe(false)
    const chart = visibleChart(wrapper)!
    expect(chart.classes()).toContain('opacity-50')
    expect(chart.classes()).toContain('transition-opacity')
    expect(chart.findAll('li')).toHaveLength(12)
    expect(visibleBars(wrapper)).toHaveLength(1)
    expect(button(wrapper, 'Go to the current year').text()).toBe('2025')

    resolveYear(monthlyStats({ year: 2025 }))
    await flushPromises()

    expect(visibleChart(wrapper)!.classes()).not.toContain('opacity-50')
    expect(visibleChart(wrapper)!.findAll('li')).toHaveLength(12)
  })

  it('says so when the selected year has no watch time, and keeps the year controls', async () => {
    const empty = monthlyStats().months.map((month) => ({ ...month, movie_minutes: 0, episode_minutes: 0 }))
    api.monthly.mockResolvedValue(monthlyStats({ months: empty }))

    const { wrapper } = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('No watch time recorded in 2026.')
    expect(wrapper.findAll('li[title]')).toHaveLength(0)
    expect(visibleBars(wrapper)).toHaveLength(1)
    expect(wrapper.find('button[aria-label="Previous year"]').exists()).toBe(true)
  })

  it('reserves the height of the chart in every state, so the page does not jump while a year loads', async () => {
    const spacer = (wrapper: ReturnType<typeof mountSection>['wrapper']) => wrapper.find('ul.invisible[aria-hidden="true"]')
    const { wrapper } = mountSection()
    expect(wrapper.findAll('.skeleton')).toHaveLength(1)
    expect(spacer(wrapper).exists()).toBe(true)
    expect(wrapper.findAll('.skeleton').every((skeleton) => skeleton.classes().includes('flex-1'))).toBe(true)
    // The all-time bar reserves its own height too, including the loading and empty states.
    expect(wrapper.find('div.invisible > p + div').exists()).toBe(true)

    await flushPromises()
    expect(spacer(wrapper).exists()).toBe(true)
    expect(spacer(wrapper).findAll('li')).toHaveLength(12)

    api.monthly.mockRejectedValueOnce({ status: 500 })
    await button(wrapper, 'Previous year').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(spacer(wrapper).exists()).toBe(true)

    const emptyMonths = monthlyStats().months.map((month) => ({ ...month, movie_minutes: 0, episode_minutes: 0 }))
    api.monthly.mockResolvedValue(monthlyStats({ months: emptyMonths }))
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('No watch time recorded in 2025.')
    expect(spacer(wrapper).exists()).toBe(true)
  })

  it('shows only the empty message when there is no watch time at all', async () => {
    const { wrapper } = mountSection({ data: watchTimeStats({ movie_minutes: 0, episode_minutes: 0, watch_time_minutes: 0 }) })
    await flushPromises()

    expect(wrapper.text()).toContain('No watch time recorded yet.')
    expect(wrapper.find('[role="group"]').exists()).toBe(false)
  })

  it('shows the chart part as an error and retries what failed', async () => {
    api.monthly.mockRejectedValueOnce({ status: 500 })

    const { wrapper } = mountSection()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Could not load stats.')

    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(api.monthly).toHaveBeenCalledTimes(2)
    expect(api.years).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('retries the all-time part through the page section', async () => {
    const { wrapper, section } = mountSection({ data: null, error: true })
    await flushPromises()

    await wrapper.get('[role="alert"] button').trigger('click')

    expect(section.load).toHaveBeenCalledTimes(1)
  })

  it('goes back to the current year when the profile changes', async () => {
    const { wrapper } = mountSection()
    await flushPromises()
    await button(wrapper, 'Previous year').trigger('click')
    await flushPromises()

    await wrapper.setProps({ username: 'carol' })
    await flushPromises()

    expect(button(wrapper, 'Go to the current year').text()).toBe('2026')
    expect(api.years).toHaveBeenLastCalledWith('carol')
    expect(api.monthly).toHaveBeenLastCalledWith('carol', 2026)
  })

  it('translates the controls and names the months in Spanish', async () => {
    usePreferencesStore().setLocale('es')

    const { wrapper } = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('Total')
    expect(wrapper.find('button[aria-label="Año anterior"]').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="Año siguiente"]').exists()).toBe(true)
    expect(wrapper.find('[role="group"]').attributes('aria-label')).toBe('Cambiar de año')
    expect(wrapper.findAll('li[title]')[0]!.attributes('title')).toContain('enero de 2026')
  })

  it('reuses the columns by position and transitions their bar heights', async () => {
    const wrapper = mount(StatColumns, {
      props: { items: [
        { key: '2026-01', label: 'Jan', value: 5 },
        { key: '2026-02', label: 'Feb', value: 10 },
      ] },
    })

    // The nodes are reused, so CSS can animate the height change instead of replacing the elements.
    await wrapper.setProps({ items: [
      { key: '2025-01', label: 'Jan', value: 10 },
      { key: '2025-02', label: 'Feb', value: 5 },
    ] })
    expect(wrapper.findAll('li')[0]!.text()).toBe('10Jan')
    expect(wrapper.get('li div > div').classes()).toContain('transition-[height]')
    expect(wrapper.get('li div > div').classes()).toContain('motion-reduce:transition-none')
  })
})
