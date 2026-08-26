import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import MediaFilterBar from '@/components/MediaFilterBar.vue'

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

function findButtonByText(wrapper, text) {
  return wrapper.findAll('button').find((button) => button.text().replace(/\s+/g, ' ').trim() === text)
}

function findAdvancedTrigger(wrapper) {
  return wrapper
    .findAll('button')
    .find((button) => button.text().replace(/\s+/g, ' ').trim().startsWith('Advanced Filters'))
}

async function applyStatusFilter(wrapper, label) {
  const trigger = findAdvancedTrigger(wrapper)
  if (!trigger) {
    throw new Error(`Advanced Filters trigger not found. Buttons: ${wrapper.findAll('button').map((button) => JSON.stringify(button.text()))}`)
  }
  await trigger.trigger('click')
  const chip = wrapper
    .findAll('button')
    .find((button) => button.classes().includes('chip') && button.text().trim() === label)
  await chip.trigger('click')
  await findButtonByText(wrapper, 'Apply').trigger('click')
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

  it('replaces stale filter params instead of merging with them', async () => {
    const { wrapper, router } = await createMountedBar({}, { status: ['dropped'] })

    // Hydration pre-selects Dropped from the URL; toggling it off and selecting
    // Watching must fully replace the status param.
    await findAdvancedTrigger(wrapper).trigger('click')
    const droppedChip = wrapper
      .findAll('button')
      .find((button) => button.classes().includes('chip') && button.text().trim() === 'Dropped')
    const watchingChip = wrapper
      .findAll('button')
      .find((button) => button.classes().includes('chip') && button.text().trim() === 'Watching')
    await droppedChip.trigger('click')
    await watchingChip.trigger('click')
    await findButtonByText(wrapper, 'Apply').trigger('click')
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
    const hydrateEvent = [...events].reverse().find(([payload]) => payload.source === 'hydrate')
    expect(hydrateEvent).toBeTruthy()
    expect(hydrateEvent[0].filters.statuses).toEqual(['watching'])
    expect(hydrateEvent[0].filters.genres).toEqual(['Drama'])
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
    const lastEvent = events[events.length - 1][0]
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
})

describe('MediaFilterBar movie profile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function createMovieBar(props = {}) {
    return createMountedBar({ mediaType: 'movie', defaultSortKey: 'title', ...props })
  }

  it('shows only the three movie status chips', async () => {
    const { wrapper } = await createMovieBar()

    await findAdvancedTrigger(wrapper).trigger('click')

    const chips = wrapper
      .findAll('button.chip')
      .map((button) => button.text().trim())
    expect(chips).toEqual(['Plan to watch', 'Watched', 'Dropped'])
    expect(chips).not.toContain('Watching')
  })

  it('offers the movie sort options without tv-only or date-added sorts', async () => {
    const { wrapper } = await createMovieBar()

    const sortDetails = wrapper.findAll('details').find((details) => details.text().includes('Sorted by'))
    await sortDetails.find('summary').trigger('click')

    const labels = sortDetails
      .findAll('button.control-option')
      .map((button) => button.text().replace('✓', '').trim())
    expect(labels).toEqual(['Title', 'Rating', 'Runtime', 'Release date', 'Watched date'])
  })

  it('applies a movie status filter to the URL', async () => {
    const { wrapper, router } = await createMovieBar()

    await applyStatusFilter(wrapper, 'Watched')

    expect(router.currentRoute.value.query).toEqual({ status: ['watched'] })
  })

  it('keeps the tv status chips for tv media type', async () => {
    const { wrapper } = await createMountedBar()

    await findAdvancedTrigger(wrapper).trigger('click')

    const chips = wrapper
      .findAll('button.chip')
      .map((button) => button.text().trim())
    expect(chips).toContain('Watching')
    expect(chips).toHaveLength(4)
  })
})
