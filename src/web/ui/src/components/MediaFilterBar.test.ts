import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import { required } from '@/test-support/assertions'
import type { VueWrapper } from '@vue/test-utils'

type FilterChange = { source: 'hydrate' | 'interaction'; filters: { search: string; statuses: string[]; genres: string[]; sort: string } }

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
      mediaType: 'tv',
      showStatusFilter: true,
      showGenreFilter: false,
      showProviderStatusFilter: false,
      showSearch: true,
      showSort: true,
      showDirection: true,
      defaultSortKey: 'added_at',
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
    const { wrapper, router } = await createMountedBar({ showGenreFilter: true })

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
    expect(lastEvent.filters.sort).toBe('added_at')
  })

  it('preserves foreign query params it does not own', async () => {
    const { wrapper, router } = await createMountedBar({}, { ref: 'profile' })

    await applyStatusFilter(wrapper, 'Watching')

    expect(router.currentRoute.value.query.ref).toBe('profile')
    expect(router.currentRoute.value.query.status).toEqual(['watching'])
  })

  it('supports the has next episode quick filter', async () => {
    const { wrapper, router } = await createMountedBar({ showQuickFilterHasNextEpisode: true })
    await required(findAdvancedTrigger(wrapper), 'Advanced Filters trigger').trigger('click')
    await required(findButtonByText(wrapper, 'Has Next Episode'), 'Has Next Episode filter').trigger('click')
    await required(findButtonByText(wrapper, 'Apply'), 'Apply button').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.has_next_episode).toBe('1')
  })

  it('hydrates and clears the has next episode quick filter', async () => {
    const { wrapper, router } = await createMountedBar({ showQuickFilterHasNextEpisode: true }, { has_next_episode: '1' })
    const hydrate = [...(wrapper.emitted('change') || [])].reverse().find(([payload]) => (payload as FilterChange).source === 'hydrate')
    expect(hydrate).toBeTruthy()

    wrapper.vm.clearAll()
    await flushPromises()
    expect(router.currentRoute.value.query.has_next_episode).toBeUndefined()
  })
})

describe('MediaFilterBar movie profile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function createMovieBar(props = {}) {
    return createMountedBar({
      mediaType: 'movie',
      defaultSortKey: 'title',
      showProviderRatingSort: true,
      showUserRatingSort: true,
      ...props,
    })
  }

  it('shows only the three movie status chips', async () => {
    const { wrapper } = await createMovieBar()

    await required(findAdvancedTrigger(wrapper), 'Advanced Filters trigger').trigger('click')

    const chips = wrapper
      .findAll('button.chip')
      .map((button) => button.text().trim())
    expect(chips).toEqual(['Plan to watch', 'Watched', 'Dropped'])
    expect(chips).not.toContain('Watching')
  })

  it('offers the movie sort options without tv-only or date-added sorts', async () => {
    const { wrapper } = await createMovieBar()

    const sortDetails = wrapper.findAll('details').find((details) => details.text().includes('Sorted by'))
    await required(sortDetails, 'Sort menu').find('summary').trigger('click')

    const labels = required(sortDetails, 'Sort menu')
      .findAll('button.control-option')
      .map((button) => button.text().replace('✓', '').trim())
    expect(labels).toEqual(['Title', 'Runtime', 'Release date', 'Provider rating', 'User rating', 'Watched date'])
  })

  it('defaults both rating sorts to descending order', async () => {
    const { wrapper } = await createMovieBar()
    const sortDetails = wrapper.findAll('details').find((details) => details.text().includes('Sorted by'))
    await required(sortDetails, 'Sort menu').find('summary').trigger('click')

    const providerRating = required(sortDetails, 'Sort menu')
      .findAll('button.control-option')
      .find((button) => button.text().includes('Provider rating'))
    await required(providerRating, 'Provider rating option').trigger('click')
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({
      filters: { sort: 'provider_rating', direction: 'desc' },
    })

    await required(sortDetails, 'Sort menu').find('summary').trigger('click')
    const userRating = required(sortDetails, 'Sort menu')
      .findAll('button.control-option')
      .find((button) => button.text().includes('User rating'))
    await required(userRating, 'User rating option').trigger('click')
    expect(wrapper.emitted('change')?.at(-1)?.[0]).toMatchObject({
      filters: { sort: 'user_rating', direction: 'desc' },
    })
  })

  it('allows provider rating without user rating', async () => {
    const { wrapper } = await createMovieBar({ showUserRatingSort: false })
    const sortDetails = wrapper.findAll('details').find((details) => details.text().includes('Sorted by'))
    await required(sortDetails, 'Sort menu').find('summary').trigger('click')

    const labels = required(sortDetails, 'Sort menu')
      .findAll('button.control-option')
      .map((button) => button.text().replace('✓', '').trim())
    expect(labels).toContain('Provider rating')
    expect(labels).not.toContain('User rating')
  })

  it('applies a movie status filter to the URL', async () => {
    const { wrapper, router } = await createMovieBar()

    await applyStatusFilter(wrapper, 'Watched')

    expect(router.currentRoute.value.query).toEqual({ status: ['watched'] })
  })

  it('keeps the tv status chips for tv media type', async () => {
    const { wrapper } = await createMountedBar()

    await required(findAdvancedTrigger(wrapper), 'Advanced Filters trigger').trigger('click')

    const chips = wrapper
      .findAll('button.chip')
      .map((button) => button.text().trim())
    expect(chips).toContain('Watching')
    expect(chips).toHaveLength(4)
  })
})
