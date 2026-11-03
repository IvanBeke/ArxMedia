import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import { required } from '@/test-support/assertions'
import type { VueWrapper } from '@vue/test-utils'

type FilterChange = {
  source: 'hydrate' | 'interaction'
  filters: { search: string; statuses: string[]; providerStatuses: string[]; genres: string[]; sort: string; direction: string; mediaType: string; missingRating: boolean }
}

vi.mock('@/api', () => ({
  mediaAPI: {
    genres: vi.fn().mockResolvedValue([]),
  },
}))

async function createMountedBar(props = {}, initialQuery = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', name: 'catch-all', component: { template: '<div />' } }],
  })
  await router.push({ path: '/my-shows', query: initialQuery })
  await router.isReady()

  const wrapper = mount(MediaFilterBar, {
    props: {
      kind: 'library',
      mediaType: 'tv',
      syncUrl: true,
      ...props,
    },
    global: {
      plugins: [router],
    },
  })
  await flushPromises()

  return { wrapper, router }
}

function findButtonByText(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((button) => button.text().replace(/\s+/g, ' ').trim() === text)
}

function findAdvancedTrigger(wrapper: VueWrapper) {
  return wrapper
    .findAll('button')
    .find((button) => button.text().replace(/\s+/g, ' ').trim().startsWith('Advanced Filters'))
}

async function openAdvanced(wrapper: VueWrapper) {
  await required(findAdvancedTrigger(wrapper), 'Advanced Filters trigger').trigger('click')
}

function sortLabels(wrapper: VueWrapper): string[] {
  const sortDetails = wrapper.findAll('details').find((details) => details.text().includes('Sorted by'))
  return required(sortDetails, 'Sort menu')
    .findAll('button.control-option')
    .map((button) => button.text().replace('✓', '').trim())
}

function sectionTitles(wrapper: VueWrapper): string[] {
  return wrapper.findAll('p.text-muted').map((title) => title.text())
}

function quickFilterLabels(wrapper: VueWrapper): string[] {
  return wrapper.findAll('button.chip-toggle').map((button) => button.text())
}

function statusChipLabels(wrapper: VueWrapper): string[] {
  return wrapper.findAll('button.chip').map((button) => button.text().trim())
}

function lastChange(wrapper: VueWrapper): FilterChange {
  return required(wrapper.emitted('change')?.at(-1), 'Last change event')[0] as FilterChange
}

async function applyStatusFilter(wrapper: VueWrapper, label: string) {
  const trigger = findAdvancedTrigger(wrapper)
  if (!trigger) {
    throw new Error(`Advanced Filters trigger not found. Buttons: ${wrapper.findAll('button').map((button) => JSON.stringify(button.text()))}`)
  }
  await trigger.trigger('click')
  const chip = wrapper
    .findAll('button')
    .find((button) => button.classes().includes('chip') && button.text().trim() === label)
  await required(chip, `${label} filter chip`).trigger('click')
  await required(findButtonByText(wrapper, 'Apply'), 'Apply button').trigger('click')
  await flushPromises()
}

describe('MediaFilterBar URL sync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('writes the filter param on apply without injecting a page param', async () => {
    const { wrapper, router } = await createMountedBar()

    await applyStatusFilter(wrapper, 'Watching')

    expect(router.currentRoute.value.query).toEqual({ status: ['watching'] })
  })

  it('pushes filter changes onto browser history so back restores the previous query', async () => {
    const { router } = await createMountedBar({}, { status: ['dropped'] })

    await router.push({ path: '/my-shows', query: { status: ['watching'] } })
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ status: ['watching'] })

    await router.back()
    await flushPromises()

    expect(router.currentRoute.value.query).toMatchObject({ status: 'dropped' })
  })

  it('replaces stale filter params instead of merging with them', async () => {
    const { wrapper, router } = await createMountedBar({}, { status: ['dropped'] })

    // Hydration pre-selects Dropped from the URL; toggling it off and selecting
    // Watching must fully replace the status param.
    await required(findAdvancedTrigger(wrapper), 'Advanced Filters trigger').trigger('click')
    const droppedChip = wrapper
      .findAll('button')
      .find((button) => button.classes().includes('chip') && button.text().trim() === 'Dropped')
    const watchingChip = wrapper
      .findAll('button')
      .find((button) => button.classes().includes('chip') && button.text().trim() === 'Watching')
    await required(droppedChip, 'Dropped filter chip').trigger('click')
    await required(watchingChip, 'Watching filter chip').trigger('click')
    await required(findButtonByText(wrapper, 'Apply'), 'Apply button').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ status: ['watching'] })
  })

  it('resets to no page param when interacting while on page 3', async () => {
    const { wrapper, router } = await createMountedBar({ page: 3 }, { page: '3' })

    await applyStatusFilter(wrapper, 'Watching')

    expect(router.currentRoute.value.query).toEqual({ status: ['watching'] })
    expect(router.currentRoute.value.query.page).toBeUndefined()
  })

  it('writes page changes from the page prop while keeping filter params', async () => {
    const { wrapper, router } = await createMountedBar({}, { status: ['watching'] })

    await wrapper.setProps({ page: 3 })
    await flushPromises()
    await router.isReady()

    expect(router.currentRoute.value.query).toEqual({ status: ['watching'], page: '3' })

    await wrapper.setProps({ page: 1 })
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ status: ['watching'] })
  })

  it('hydrates filter state from external query changes and emits hydrate', async () => {
    const { wrapper, router } = await createMountedBar()

    await router.replace({ path: '/my-shows', query: { status: ['watching'], genres: ['Drama'] } })
    await flushPromises()

    const events = wrapper.emitted('change') || []
    const hydrateEvent = [...events].reverse().find(([payload]) => (payload as FilterChange).source === 'hydrate')
    expect(hydrateEvent).toBeTruthy()
    expect((required(hydrateEvent, 'Hydrate event')[0] as FilterChange).filters.statuses).toEqual(['watching'])
    expect((required(hydrateEvent, 'Hydrate event')[0] as FilterChange).filters.genres).toEqual(['Drama'])
  })

  it('clearAll resets every filter and clears owned params from the URL', async () => {
    const { wrapper, router } = await createMountedBar({}, { page: '2' })

    await applyStatusFilter(wrapper, 'Watching')
    const searchInput = wrapper.find('input[type="text"]')
    await searchInput.setValue('thriller')
    await searchInput.trigger('keydown.enter')
    await flushPromises()

    expect(router.currentRoute.value.query.search).toBe('thriller')

    wrapper.vm.clearAll()
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({})
    const events = wrapper.emitted('change') || []
    const lastEvent = required(events.at(-1), 'Last change event')[0] as FilterChange
    expect(lastEvent.source).toBe('interaction')
    expect(lastEvent.filters.search).toBe('')
    expect(lastEvent.filters.statuses).toEqual([])
    expect(lastEvent.filters.sort).toBe('last_watched')
  })

  it('preserves foreign query params it does not own', async () => {
    const { wrapper, router } = await createMountedBar({}, { ref: 'profile' })

    await applyStatusFilter(wrapper, 'Watching')

    expect(router.currentRoute.value.query.ref).toBe('profile')
    expect(router.currentRoute.value.query.status).toEqual(['watching'])
  })

  it('supports the has next episode quick filter', async () => {
    const { wrapper, router } = await createMountedBar()
    await required(findAdvancedTrigger(wrapper), 'Advanced Filters trigger').trigger('click')
    await required(findButtonByText(wrapper, 'Has Next Episode'), 'Has Next Episode filter').trigger('click')
    await required(findButtonByText(wrapper, 'Apply'), 'Apply button').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.has_next_episode).toBe('1')
  })

  it('hydrates and clears the has next episode quick filter', async () => {
    const { wrapper, router } = await createMountedBar({}, { has_next_episode: '1' })
    const hydrate = [...(wrapper.emitted('change') || [])].reverse().find(([payload]) => (payload as FilterChange).source === 'hydrate')
    expect(hydrate).toBeTruthy()

    wrapper.vm.clearAll()
    await flushPromises()
    expect(router.currentRoute.value.query.has_next_episode).toBeUndefined()
  })
})

describe('MediaFilterBar genres', () => {
  it('offers the genres returned by the API', async () => {
    const { mediaAPI } = await import('@/api')
    vi.mocked(mediaAPI.genres).mockResolvedValueOnce([
      { tmdb_id: 18, name: 'Drama' },
      { tmdb_id: 28, name: 'Action' },
    ])
    const { wrapper } = await createMountedBar()

    await openAdvanced(wrapper)

    expect(statusChipLabels(wrapper)).toEqual(expect.arrayContaining(['Drama', 'Action']))
  })
})

describe('MediaFilterBar library profile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function createMovieBar(props = {}, query = {}) {
    return createMountedBar({ mediaType: 'movie', ...props }, query)
  }

  it('shows only the three movie status chips', async () => {
    const { wrapper } = await createMovieBar()

    await openAdvanced(wrapper)

    expect(statusChipLabels(wrapper)).toEqual(['Plan to watch', 'Watched', 'Dropped'])
  })

  it('keeps the tv status chips and the tv-only filters for tv', async () => {
    const { wrapper } = await createMountedBar({ providerStatusOptions: ['Ended'] })

    await openAdvanced(wrapper)

    expect(statusChipLabels(wrapper).slice(0, 4)).toEqual(['Plan to watch', 'Watching', 'Watched', 'Dropped'])
    expect(sectionTitles(wrapper)).toEqual(['Quick filters', 'User status', 'Show status', 'Genres'])
    expect(quickFilterLabels(wrapper)).toEqual(['Has upcoming', 'New episodes', 'Missing rating', 'Has Next Episode'])
  })

  it('offers no tv-only filters for movies', async () => {
    const { wrapper } = await createMovieBar()

    await openAdvanced(wrapper)

    expect(sectionTitles(wrapper)).toEqual(['Quick filters', 'User status', 'Genres'])
    expect(quickFilterLabels(wrapper)).toEqual(['Missing rating'])
  })

  it('offers the movie sorts', async () => {
    const { wrapper } = await createMovieBar()

    expect(sortLabels(wrapper)).toEqual([
      'Title', 'Votes', 'Runtime', 'Release date', 'Provider rating', 'User rating', 'Watched date',
    ])
    expect(lastChange(wrapper).filters.sort).toBe('watched_date')
  })

  it('offers the tv sorts', async () => {
    const { wrapper } = await createMountedBar()

    expect(sortLabels(wrapper)).toEqual([
      'Title', 'Votes', 'Runtime', 'Release date', 'Provider rating', 'User rating',
      'Episode runtime', 'Last watched', 'Started date', 'Progress', 'Next episode date', 'Episodes left', 'Time left',
    ])
    expect(lastChange(wrapper).filters.sort).toBe('last_watched')
  })

  it('defaults votes and ratings to descending order', async () => {
    const { wrapper } = await createMovieBar()
    const sortDetails = required(wrapper.findAll('details').find((details) => details.text().includes('Sorted by')), 'Sort menu')

    const expectations: [string, string][] = [['Provider rating', 'provider_rating'], ['User rating', 'user_rating'], ['Votes', 'vote_count']]
    for (const [label, sort] of expectations) {
      const option = sortDetails.findAll('button.control-option').find((button) => button.text().includes(label))
      await required(option, `${label} option`).trigger('click')
      expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({ filters: { sort, direction: 'desc' } })
    }
  })

  it('defaults episode runtime to ascending order', async () => {
    const { wrapper } = await createMountedBar()
    const sortDetails = required(wrapper.findAll('details').find((details) => details.text().includes('Sorted by')), 'Sort menu')

    const option = sortDetails.findAll('button.control-option').find((button) => button.text().includes('Episode runtime'))
    await required(option, 'Episode runtime option').trigger('click')

    expect(lastChange(wrapper).filters).toMatchObject({ sort: 'episode_runtime', direction: 'asc' })
  })

  it('applies a movie status filter to the URL', async () => {
    const { wrapper, router } = await createMovieBar()

    await applyStatusFilter(wrapper, 'Watched')

    expect(router.currentRoute.value.query).toEqual({ status: ['watched'] })
  })

  it('drops started-only sorts and the missing rating filter when only plan to watch is selected', async () => {
    const { wrapper } = await createMountedBar({}, { status: ['plan_to_watch'] })

    expect(sortLabels(wrapper)).toEqual([
      'Title', 'Votes', 'Runtime', 'Release date', 'Provider rating', 'User rating', 'Episode runtime',
    ])
    expect(lastChange(wrapper).filters.sort).toBe('title')

    await openAdvanced(wrapper)
    expect(quickFilterLabels(wrapper)).not.toContain('Missing rating')
  })

  it('keeps started-only sorts once a started status is selected', async () => {
    const { wrapper } = await createMountedBar({}, { status: ['plan_to_watch', 'watching'] })

    expect(sortLabels(wrapper)).toContain('Last watched')
  })

  it('falls back to the default sort when the status filter removes the current sort', async () => {
    const { wrapper, router } = await createMovieBar()
    expect(lastChange(wrapper).filters.sort).toBe('watched_date')

    await applyStatusFilter(wrapper, 'Plan to watch')

    expect(lastChange(wrapper).filters).toMatchObject({ sort: 'title', statuses: ['plan_to_watch'] })
    // Title is now the resolved default, so it is not written to the URL.
    expect(router.currentRoute.value.query).toEqual({ status: ['plan_to_watch'] })
  })

  it('prunes values that do not apply to the media type when hydrating from the URL', async () => {
    const { wrapper } = await createMovieBar({}, {
      status: ['watching', 'watched'],
      provider_status: ['Ended'],
      has_upcoming: '1',
      sort: 'last_watched',
    })

    expect(lastChange(wrapper).filters).toMatchObject({
      statuses: ['watched'],
      providerStatuses: [],
      sort: 'watched_date',
    })
  })
})

describe('MediaFilterBar watchlist profile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const baseSorts = ['Date added', 'Title', 'Votes', 'Runtime', 'Release date', 'Provider rating']

  async function createWatchlistBar(query = {}, props = {}) {
    return createMountedBar({ kind: 'watchlist', mediaType: 'all', providerStatusOptions: ['Ended', 'Returning Series'], ...props }, query)
  }

  it('offers the base sorts for all media types and never started-only sorts', async () => {
    const { wrapper } = await createWatchlistBar()

    expect(sortLabels(wrapper)).toEqual(baseSorts)
    expect(lastChange(wrapper).filters.sort).toBe('added_at')
  })

  it('keeps the base sorts for movies', async () => {
    const { wrapper } = await createWatchlistBar({ media_type: 'movie' })

    expect(sortLabels(wrapper)).toEqual(baseSorts)
  })

  it('adds episode runtime for shows without dropping anything', async () => {
    const { wrapper } = await createWatchlistBar({ media_type: 'tv' })

    expect(sortLabels(wrapper)).toEqual([...baseSorts, 'Episode runtime'])
  })

  it('has no status or quick filters, but offers show status for shows', async () => {
    const { wrapper } = await createWatchlistBar()
    await openAdvanced(wrapper)

    expect(sectionTitles(wrapper)).toEqual(['Genres', 'Media type'])
    expect(quickFilterLabels(wrapper)).toEqual([])

    const shows = required(findButtonByText(wrapper, 'Shows'), 'Shows chip')
    await shows.trigger('click')
    expect(sectionTitles(wrapper)).toEqual(['Show status', 'Genres', 'Media type'])
  })

  it('hides show status when the server provides no options', async () => {
    const { wrapper } = await createWatchlistBar({ media_type: 'tv' }, { providerStatusOptions: [] })
    await openAdvanced(wrapper)

    expect(sectionTitles(wrapper)).toEqual(['Genres', 'Media type'])
  })

  it('keeps a show status from the URL before the options have loaded', async () => {
    const { wrapper } = await createWatchlistBar({ media_type: 'tv', provider_status: ['Ended'] }, { providerStatusOptions: [] })

    expect(lastChange(wrapper).filters.providerStatuses).toEqual(['Ended'])
  })

  it('lists the options provided by the server as show statuses', async () => {
    const { wrapper } = await createWatchlistBar({ media_type: 'tv' })
    await openAdvanced(wrapper)

    expect(statusChipLabels(wrapper).slice(0, 2)).toEqual(['Ended', 'Returning Series'])
  })

  it('applies a show status to the URL', async () => {
    const { wrapper, router } = await createWatchlistBar({ media_type: 'tv' })

    await openAdvanced(wrapper)
    const chip = wrapper.findAll('button.chip').find((button) => button.text().trim() === 'Ended')
    await required(chip, 'Ended chip').trigger('click')
    await required(findButtonByText(wrapper, 'Apply'), 'Apply button').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ media_type: 'tv', provider_status: ['Ended'] })
    expect(lastChange(wrapper).filters.providerStatuses).toEqual(['Ended'])
  })

  it('ignores a status filter from the URL since every item is on the watchlist', async () => {
    const { wrapper } = await createWatchlistBar({ status: ['watched'], missing_rating: '1' })

    expect(lastChange(wrapper).filters).toMatchObject({ statuses: [], missingRating: false })
  })
})

describe('MediaFilterBar list profile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const baseSorts = [
    'Custom order', 'Date added', 'Title', 'Votes', 'Runtime', 'Release date', 'Provider rating', 'User rating',
  ]

  async function createListBar(query = {}) {
    return createMountedBar({ kind: 'list', mediaType: 'all', providerStatusOptions: ['Ended'] }, query)
  }

  it('offers the base sorts for all media types and defaults to custom order', async () => {
    const { wrapper } = await createListBar()

    expect(sortLabels(wrapper)).toEqual(baseSorts)
    expect(lastChange(wrapper).filters.sort).toBe('custom_order')
  })

  it('expands the sorts for movies', async () => {
    const { wrapper } = await createListBar({ media_type: 'movie' })

    expect(sortLabels(wrapper)).toEqual([...baseSorts, 'Watched date'])
  })

  it('expands the sorts for shows', async () => {
    const { wrapper } = await createListBar({ media_type: 'tv' })

    expect(sortLabels(wrapper)).toEqual([
      ...baseSorts, 'Episode runtime', 'Last watched', 'Started date', 'Progress', 'Next episode date', 'Episodes left', 'Time left',
    ])
  })

  it('shows the list filters for all media types and adds show status for shows', async () => {
    const { wrapper } = await createListBar()
    await openAdvanced(wrapper)

    expect(sectionTitles(wrapper)).toEqual(['Quick filters', 'User status', 'Genres', 'Media type'])
    expect(quickFilterLabels(wrapper)).toEqual(['Missing rating', 'In watchlist'])

    await required(findButtonByText(wrapper, 'Shows'), 'Shows chip').trigger('click')
    expect(sectionTitles(wrapper)).toEqual(['Quick filters', 'User status', 'Show status', 'Genres', 'Media type'])
  })

  it('follows the staged media type for the status chips before applying', async () => {
    const { wrapper } = await createListBar()
    await openAdvanced(wrapper)
    expect(statusChipLabels(wrapper).slice(0, 4)).toEqual(['Plan to watch', 'Watching', 'Watched', 'Dropped'])

    await required(findButtonByText(wrapper, 'Movies'), 'Movies chip').trigger('click')

    expect(statusChipLabels(wrapper).slice(0, 3)).toEqual(['Plan to watch', 'Watched', 'Dropped'])
    expect(statusChipLabels(wrapper)).not.toContain('Watching')
  })

  it('falls back to custom order when widening the media type drops the current sort', async () => {
    const { wrapper, router } = await createListBar({ media_type: 'tv', sort: 'last_watched' })
    expect(lastChange(wrapper).filters.sort).toBe('last_watched')

    await openAdvanced(wrapper)
    await required(findButtonByText(wrapper, 'Shows'), 'Shows chip').trigger('click')
    await required(findButtonByText(wrapper, 'Apply'), 'Apply button').trigger('click')
    await flushPromises()

    expect(lastChange(wrapper).filters).toMatchObject({ mediaType: 'all', sort: 'custom_order' })
    expect(router.currentRoute.value.query.sort).toBeUndefined()
  })

  it('clears stale show filters when the media type no longer supports them', async () => {
    const { wrapper, router } = await createListBar({ media_type: 'tv', provider_status: ['Ended'], status: ['watching'] })
    expect(lastChange(wrapper).filters).toMatchObject({ providerStatuses: ['Ended'], statuses: ['watching'] })

    await router.replace({ path: '/my-shows', query: { media_type: 'movie', provider_status: ['Ended'], status: ['watching'] } })
    await flushPromises()

    expect(lastChange(wrapper).filters).toMatchObject({ mediaType: 'movie', providerStatuses: [], statuses: [] })
  })
})

