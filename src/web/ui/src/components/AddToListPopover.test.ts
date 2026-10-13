import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import AddToListPopover from '@/components/AddToListPopover.vue'
import { Lock, LockOpen } from '@lucide/vue'
import { trackingAPI } from '@/api'
import type { CustomList, ListItem } from '@/types/api'

vi.mock('@/api', () => ({
  trackingAPI: {
    getLists: vi.fn().mockResolvedValue({ count: 0, next: null, previous: null, results: [] }),
    addToList: vi.fn(),
    createList: vi.fn(),
    removeFromList: vi.fn(),
  },
}))

const mockedAPI = vi.mocked(trackingAPI)

function mountPopover() {
  return mount(AddToListPopover, {
    props: { mediaType: 'movie', tmdbId: 42, startOpen: true },
    global: { plugins: [createPinia()] },
  })
}

function listRow(name: string, contained: boolean, itemId: number | null = null, privacy: CustomList['privacy'] = 'private'): CustomList {
  return {
    id: name === 'Favorites' ? 1 : 2,
    username: 'tester',
    name,
    description: '',
    privacy,
    item_count: contained ? 1 : 0,
    collaborators: [],
    collaborator_users: [],
    contains_item: contained,
    contains_item_id: itemId,
    created_at: '',
    updated_at: '',
  }
}

describe('AddToListPopover', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedAPI.getLists.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
  })

  it('keeps the desktop dropdown anchored to the button', () => {
    const panel = mountPopover().find('.absolute')

    expect(panel.exists()).toBe(true)
    expect(panel.classes()).toContain('right-0')
    expect(panel.classes()).toContain('w-72')
  })

  it('passes positioning through to the actions bar below the sm breakpoint', () => {
    const wrapper = mountPopover()

    expect(wrapper.classes()).toContain('max-sm:static')
  })

  it('docks the panel above the actions row below the sm breakpoint', () => {
    const panel = mountPopover().find('.absolute')

    expect(panel.classes()).toContain('max-sm:inset-x-0')
    expect(panel.classes()).toContain('max-sm:bottom-full')
    expect(panel.classes()).toContain('max-sm:w-auto')
  })

  it('keeps modal mode full width without floating positioning', () => {
    const wrapper = mount(AddToListPopover, {
      props: { mediaType: 'movie', tmdbId: 42, modalMode: true },
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.find('.absolute').exists()).toBe(false)
    expect(wrapper.find('.w-full').exists()).toBe(true)
  })

  it('loads lists with membership params and renders checkbox state', async () => {
    mockedAPI.getLists.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [listRow('Favorites', true, 99), listRow('Watch later', false)],
    })

    const wrapper = mountPopover()
    await flushPromises()

    expect(mockedAPI.getLists).toHaveBeenCalledWith({ media_type: 'movie', tmdb_id: 42 })
    const rows = wrapper.findAll('button[aria-pressed]')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.attributes('aria-pressed')).toBe('true')
    expect(rows[1]?.attributes('aria-pressed')).toBe('false')
  })

  it('adds an uncontained item when its full row is clicked', async () => {
    mockedAPI.getLists.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [listRow('Watch later', false)],
    })
    mockedAPI.addToList.mockResolvedValue({ id: 77 } as unknown as ListItem)

    const wrapper = mountPopover()
    await flushPromises()

    await wrapper.find('button[aria-pressed="false"]').trigger('click')
    await flushPromises()

    expect(mockedAPI.addToList).toHaveBeenCalledWith(2, { media_type: 'movie', tmdb_id: 42 })
    expect(wrapper.find('button[aria-pressed="true"]').exists()).toBe(true)
    expect(wrapper.emitted('added')).toBeTruthy()
  })

  it('removes a contained item when its full row is clicked', async () => {    mockedAPI.getLists.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [listRow('Favorites', true, 99)],
    })
    mockedAPI.removeFromList.mockResolvedValue(undefined)

    const wrapper = mountPopover()
    await flushPromises()

    await wrapper.find('button[aria-pressed="true"]').trigger('click')
    await flushPromises()

    expect(mockedAPI.removeFromList).toHaveBeenCalledWith(1, 99)
    expect(wrapper.find('button[aria-pressed="false"]').exists()).toBe(true)
    expect(wrapper.emitted('removed')).toBeTruthy()
  })

  it('shows a closed lock for private lists and an open lock for public lists', async () => {
    mockedAPI.getLists.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [listRow('Favorites', true, 99, 'private'), listRow('Shared', false, null, 'public')],
    })

    const wrapper = mountPopover()
    await flushPromises()

    const rows = wrapper.findAll('button[aria-pressed]')
    expect(rows[0]?.findComponent(Lock).exists()).toBe(true)
    expect(rows[0]?.findComponent(LockOpen).exists()).toBe(false)
    expect(rows[1]?.findComponent(LockOpen).exists()).toBe(true)
    expect(rows[1]?.findComponent(Lock).exists()).toBe(false)
    expect(wrapper.text()).not.toContain('(private)')
  })
})
