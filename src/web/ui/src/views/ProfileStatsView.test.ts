import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProfileStatsView from '@/views/ProfileStatsView.vue'
import StatPie from '@/components/StatPie.vue'
import StatStackedBar from '@/components/StatStackedBar.vue'
import WatchTimeSection from '@/components/WatchTimeSection.vue'
import LoadError from '@/components/LoadError.vue'
import UserStatCards from '@/components/UserStatCards.vue'
import { usePreferencesStore } from '@/stores/preferences'
import type { StatSliceInput } from '@/types/stats'
import { habitsStats, libraryStats, mockStatsAPI, monthlyStats, ratingStats, watchCountStats, watchTimeStats } from '@/test-support/stats'

async function mountView(username = 'bob') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/profile/:username/stats', component: ProfileStatsView },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
  })
  await router.push(`/profile/${username}/stats`)
  await router.isReady()
  const wrapper = mount(ProfileStatsView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('ProfileStatsView', () => {
  let api: ReturnType<typeof mockStatsAPI>

  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    api = mockStatsAPI()
  })

  it('loads every stats section of the profile in the URL and shows the page title', async () => {
    const { wrapper } = await mountView()

    for (const spy of [api.ratings, api.library, api.watchCount, api.watchTime, api.years, api.habits]) {
      expect(spy).toHaveBeenCalledWith('bob')
    }
    // The monthly chart waits for the current year.
    expect(api.monthly).toHaveBeenCalledWith('bob', 2026)
    expect(wrapper.get('h1').text()).toBe('Stats')
    expect(document.title).toBe('Stats · ArxMedia')
    expect(wrapper.get('a[href="/profile/bob"]').text()).toContain('Back to profile')
  })

  it('shows all eight cards', async () => {
    const { wrapper } = await mountView()

    const grid = wrapper.getComponent(UserStatCards)
    const cards = grid.findAll('p.text-2xl').map((value) => value.text())
    const titles = grid.findAll('p.text-xs').map((title) => title.text())

    expect(titles).toEqual([
      'Movies Watched', 'Shows Watched', 'Episodes Watched', 'Shows Watching',
      'Watch time', 'Ratings', 'Watchlist', 'Avg. Rating',
    ])
    expect(cards).toEqual(['12', '3', '40', '2', '2h 30m', '4', '3', '8'])
  })

  it('shows an em dash when there is no average rating', async () => {
    api.ratings.mockResolvedValue(ratingStats({ average_rating: null, ratings_count: 0, rating_distribution: Array<number>(10).fill(0) }))

    const { wrapper } = await mountView()

    expect(wrapper.findAll('.card p.text-2xl').at(-1)?.text()).toBe('–')
  })

  it('renders the rating distribution, library pie, status breakdown and watch time split', async () => {
    const { wrapper } = await mountView()
    const text = wrapper.text()
    const sections = wrapper.findAll('section')

    expect(text).toContain('Rating distribution')
    expect(sections[2]!.findAll('li')).toHaveLength(10)

    expect(text).toContain('Library by type')
    const pie = wrapper.findAllComponents(StatPie).at(-1)!
    expect((pie.props() as { items: StatSliceInput[] }).items.map((item) => [item.label, item.value])).toEqual([['Movies', 13], ['Shows', 6]])
    expect(pie.text()).toContain('68%')

    expect(text).toContain('Status breakdown')
    const statuses = sections[0]!
    expect(statuses.text()).toContain('Shows')
    expect(statuses.text()).toContain('Movies')
    expect(statuses.findAllComponents(StatPie).map((pie: VueWrapper) => (pie.props() as { items: StatSliceInput[] }).items.map((item) => [item.key, item.value]))).toEqual([
      [['watching', 2], ['watched', 3], ['plan_to_watch', 1], ['dropped', 0]],
      [['watched', 10], ['plan_to_watch', 2], ['dropped', 1]],
    ])

    expect(text).toContain('Watch time breakdown')
    expect(sections[1]!.getComponent(WatchTimeSection).props('username')).toBe('bob')
    expect(sections[1]!.findAll('li[title]')).toHaveLength(12)
  })

  it('shows an empty message for a status pie whose media type has nothing tracked', async () => {
    api.library.mockResolvedValue(libraryStats({
      movie_statuses: { plan_to_watch: 0, watched: 0, dropped: 0 },
      media_types: { movie: 0, tv: 6 },
    }))

    const { wrapper } = await mountView()
    const statuses = wrapper.findAll('section')[0]!

    expect(statuses.findAllComponents(StatPie)).toHaveLength(1)
    expect(statuses.text()).toContain('Nothing tracked yet.')
  })

  it('orders the sections as statuses, watch time, rating distribution and library, then watch activity', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.findAll('section').map((section) => section.get('h2').text())).toEqual([
      'Status breakdown', 'Watch time breakdown', 'Rating distribution', 'Library by type',
      'Watched movies by day', 'Watched episodes by day', 'Watched movies by time', 'Watched episodes by time',
    ])
  })

  it('renders the watched-by-day and watched-by-time charts for movies and episodes', async () => {
    const { wrapper } = await mountView()
    const sections = wrapper.findAll('section')

    expect(sections.slice(4).map((section) => section.get('h2').text())).toEqual([
      'Watched movies by day', 'Watched episodes by day', 'Watched movies by time', 'Watched episodes by time',
    ])

    const moviesByDay = sections[4]!.findAll('li')
    expect(moviesByDay.map((column) => column.findAll('span').at(-1)!.text())).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    expect(moviesByDay[6]!.attributes('title')).toBe('Sunday: 3')

    const episodesByTime = sections[7]!.findAll('li')
    expect(episodesByTime).toHaveLength(24)
    expect(episodesByTime.map((column) => column.findAll('span').at(-1)!.text()).slice(0, 3)).toEqual(['00', '01', '02'])
    expect(episodesByTime[23]!.findAll('span').at(-1)!.text()).toBe('23')
    expect(episodesByTime[20]!.attributes('title')).toBe('20:00: 9')
    expect(sections[6]!.findAll('li')[21]!.attributes('title')).toBe('21:00: 4')
    expect(sections[6]!.findAll('li')[21]!.findAll('span')[0]!.text()).toBe('4')
    expect(sections[4]!.findAll('li').map((column) => column.findAll('span')[0]!.text())).toEqual(['1', '', '2', '', '', '', '3'])
  })

  it('gives each by-time chart a full row and keeps the by-day charts side by side', async () => {
    const { wrapper } = await mountView()

    const spansFullRow = wrapper.findAll('section').slice(4).map((section) => section.classes().includes('lg:col-span-2'))
    expect(spansFullRow).toEqual([false, false, true, true])
  })

  it('uses the 24-hour clock without am/pm in the time charts', async () => {
    const { wrapper } = await mountView()

    const labels = wrapper.findAll('section')[6]!.findAll('li').map((column) => column.findAll('span').at(-1)!.text())
    expect(labels).toEqual(Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0')))
  })

  it('shows empty states for the insight sections without data', async () => {
    const none = (size: number) => Array<number>(size).fill(0)
    api.watchCount.mockResolvedValue(watchCountStats({ movies_watched: 0, episodes_watched: 0 }))
    api.watchTime.mockResolvedValue(watchTimeStats({ movie_minutes: 0, episode_minutes: 0, watch_time_minutes: 0 }))
    api.ratings.mockResolvedValue(ratingStats({ ratings_count: 0, average_rating: null, rating_distribution: none(10) }))
    api.library.mockResolvedValue(libraryStats({
      show_statuses: { plan_to_watch: 0, watching: 0, watched: 0, dropped: 0 },
      movie_statuses: { plan_to_watch: 0, watched: 0, dropped: 0 },
      media_types: { movie: 0, tv: 0 },
      watchlist_count: 0,
    }))
    api.habits.mockResolvedValue(habitsStats({
      movie: { weekdays: none(7), hours: none(24) },
      episode: { weekdays: none(7), hours: none(24) },
    }))

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('No ratings yet.')
    expect(wrapper.text()).toContain('Nothing tracked yet.')
    expect(wrapper.findComponent(StatPie).exists()).toBe(false)
    expect(wrapper.findAllComponents(StatStackedBar).filter((bar: VueWrapper) => !bar.element.closest('.invisible'))).toHaveLength(0)
    expect(wrapper.text()).toContain('No watch time recorded yet.')
    expect(wrapper.text().match(/No watch dates recorded yet\./g)).toHaveLength(4)
  })

  it('shows the locked message when the profile is hidden', async () => {
    for (const spy of Object.values(api)) spy.mockRejectedValue({ status: 403 })

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Stats are hidden by this account privacy setting.')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.findAll('section')).toHaveLength(0)
  })

  it('shows the failing section as an error with a retry, and the rest of the page as usual', async () => {
    api.ratings.mockRejectedValueOnce({ status: 500 })

    const { wrapper } = await mountView()
    const ratingSection = wrapper.findAll('section')[2]!

    expect(ratingSection.get('[role="alert"]').text()).toContain('Could not load stats.')
    expect(wrapper.getComponent(LoadError).text()).toContain('Could not load stats.')
    expect(wrapper.findAll('section')[0]!.findAllComponents(StatPie)).toHaveLength(2)
    expect(api.habits).toHaveBeenCalledTimes(1)

    await ratingSection.get('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(api.ratings).toHaveBeenCalledTimes(2)
    expect(api.watchCount).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.getComponent(UserStatCards).findAll('.card')).toHaveLength(8)
  })

  it('retries only the sections that failed from the cards error', async () => {
    api.ratings.mockRejectedValueOnce({ status: 500 })
    api.library.mockRejectedValueOnce({ status: 500 })

    const { wrapper } = await mountView()
    await wrapper.getComponent(LoadError).get('button').trigger('click')
    await flushPromises()

    expect(api.ratings).toHaveBeenCalledTimes(2)
    expect(api.library).toHaveBeenCalledTimes(2)
    expect(api.watchCount).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('fills in sections as their own data arrives', async () => {
    let resolveMonthly: (value: ReturnType<typeof monthlyStats>) => void = () => {}
    api.monthly.mockReturnValue(new Promise((resolve) => { resolveMonthly = resolve }))

    const { wrapper } = await mountView()

    expect(wrapper.getComponent(UserStatCards).findAll('.card')).toHaveLength(8)
    expect(wrapper.findAll('section')[1]!.find('.skeleton').exists()).toBe(true)
    expect(wrapper.findAll('section')[1]!.findAllComponents(StatStackedBar).filter((bar: VueWrapper) => !bar.element.closest('.invisible'))).toHaveLength(1)

    resolveMonthly(monthlyStats())
    await flushPromises()

    expect(wrapper.findAll('section')[1]!.find('.skeleton').exists()).toBe(false)
    expect(wrapper.findAll('section')[1]!.findAll('li[title]')).toHaveLength(12)
  })

  it('reloads every section when navigating to another profile', async () => {
    const { wrapper, router } = await mountView()

    await router.push('/profile/carol/stats')
    await flushPromises()

    for (const spy of [api.ratings, api.library, api.watchCount, api.watchTime, api.years, api.habits]) {
      expect(spy).toHaveBeenLastCalledWith('carol')
    }
    expect(api.monthly).toHaveBeenLastCalledWith('carol', 2026)
    expect(wrapper.get('h1').text()).toBe('Stats')
  })

  it('translates the page to Spanish', async () => {
    usePreferencesStore().setLocale('es')

    const { wrapper } = await mountView()
    const text = wrapper.text()

    expect(wrapper.get('h1').text()).toBe('Estadísticas')
    expect(text).toContain('Películas vistas')
    expect(text).toContain('Distribución de valoraciones')
    expect(text).toContain('Biblioteca por tipo')
    expect(text).toContain('Desglose por estado')
    expect(text).toContain('Películas vistas por día')
    expect(text).toContain('Episodios vistos por hora')
    expect(wrapper.findAll('section')[4]!.findAll('li').map((column) => column.findAll('span').at(-1)!.text())).toEqual(['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'])
    expect(text).toContain('Total')
    expect(wrapper.find('[aria-label="Año anterior"]').exists()).toBe(true)
  })
})
