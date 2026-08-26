import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ListDetailView from '@/views/ListDetailView.vue'

const getList = vi.fn()
const getListItems = vi.fn()
const reorderList = vi.fn()

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    trackingAPI: {
      getList: (...args) => getList(...args),
      getListItems: (...args) => getListItems(...args),
      reorderList: (...args) => reorderList(...args),
      updateList: vi.fn().mockResolvedValue({}),
      deleteList: vi.fn().mockResolvedValue({}),
      addToList: vi.fn().mockResolvedValue({}),
      removeFromList: vi.fn().mockResolvedValue({}),
      addCollaborator: vi.fn().mockResolvedValue({}),
      removeCollaborator: vi.fn().mockResolvedValue({}),
    },
    authAPI: {
      searchUsers: vi.fn().mockResolvedValue([]),
    },
    mediaAPI: {
      search: vi.fn().mockResolvedValue({ results: [] }),
      genres: vi.fn().mockResolvedValue([]),
    },
  }
})

vi.mock('@/stores/auth', async () => {
  const { defineStore } = await import('pinia')
  return {
    useAuthStore: defineStore('auth', {
      state: () => ({
        user: { id: 1, username: 'owner' },
      }),
    }),
  }
})

function paged(items) {
  return {
    count: items.length,
    next: null,
    previous: null,
    results: items,
  }
}

async function mountView(listId = '1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/lists/:id', name: 'list-detail', component: ListDetailView }],
  })
  await router.push(`/lists/${listId}`)
  await router.isReady()
  setActivePinia(createPinia())
  const wrapper = mount(ListDetailView, {
    global: {
      plugins: [router],
      stubs: {
        MediaCard: { template: '<div class="media-card-stub" />' },
        PaginationControls: { template: '<div />', props: ['count'] },
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ListDetailView custom_order', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getList.mockResolvedValue({
      id: 1,
      name: 'Test List',
      username: 'owner',
      privacy: 'private',
      collaborators: [1],
      collaborator_users: [],
      created_at: new Date().toISOString(),
      item_count: 3,
    })
    getListItems.mockResolvedValue(paged([
      { id: 10, media_type: 'movie', tmdb_id: 101, custom_order: 0, title: 'A' },
      { id: 11, media_type: 'movie', tmdb_id: 102, custom_order: 1, title: 'B' },
      { id: 12, media_type: 'movie', tmdb_id: 103, custom_order: 2, title: 'C' },
    ]))
    reorderList.mockResolvedValue({ ordered: true, custom_order: [12, 11, 10] })
  })

  it('defaults to custom_order sorting', async () => {
    const wrapper = await mountView()
    // MediaFilterBar should be initialized with custom_order
    expect(getListItems).toHaveBeenCalledWith('1', expect.objectContaining({ sort: 'custom_order', direction: 'asc' }))
    expect(wrapper.text()).not.toContain('Could not load')
  })

  it('allows reorder anytime when canEdit', async () => {
    const wrapper = await mountView()
    await flushPromises()
    const btn = wrapper.find('button')
    // Find Reorder button
    const reorderBtn = wrapper.findAll('button').find((b) => b.text().includes('Reorder'))
    expect(reorderBtn).toBeTruthy()
    expect(reorderBtn.attributes('disabled')).toBeUndefined()
  })

  it('enters reorder mode and batches save on Done', async () => {
    const wrapper = await mountView()
    await flushPromises()
    getListItems.mockClear()
    getListItems.mockResolvedValue(paged([
      { id: 10, media_type: 'movie', tmdb_id: 101, custom_order: 0 },
      { id: 11, media_type: 'movie', tmdb_id: 102, custom_order: 1 },
      { id: 12, media_type: 'movie', tmdb_id: 103, custom_order: 2 },
    ]))
    const reorderBtn = wrapper.findAll('button').find((b) => b.text().includes('Reorder'))
    await reorderBtn.trigger('click')
    await flushPromises()
    expect(getListItems).toHaveBeenCalledWith('1', expect.objectContaining({ sort: 'custom_order', direction: 'asc', page: 1 }))
    // Simulate drag: move first to last via component method
    // Directly test that Done triggers single reorder call
    const vm = wrapper.vm
    // items are already loaded, simulate hasReordered
    vm.hasReordered = true
    vm.items = [
      { id: 12, media_type: 'movie', tmdb_id: 103, custom_order: 2 },
      { id: 11, media_type: 'movie', tmdb_id: 102, custom_order: 1 },
      { id: 10, media_type: 'movie', tmdb_id: 101, custom_order: 0 },
    ]
    const doneBtn = wrapper.findAll('button').find((b) => b.text() === 'Done')
    expect(doneBtn).toBeTruthy()
    await doneBtn.trigger('click')
    await flushPromises()
    expect(reorderList).toHaveBeenCalledTimes(1)
    expect(reorderList).toHaveBeenCalledWith('1', [12, 11, 10])
  })

  it('Cancel discards without saving', async () => {
    const wrapper = await mountView()
    await flushPromises()
    const reorderBtn = wrapper.findAll('button').find((b) => b.text().includes('Reorder'))
    await reorderBtn.trigger('click')
    await flushPromises()
    const vm = wrapper.vm
    vm.hasReordered = true
    vm.items = [
      { id: 12, media_type: 'movie', tmdb_id: 103 },
      { id: 10, media_type: 'movie', tmdb_id: 101 },
    ]
    const cancelBtn = wrapper.findAll('button').find((b) => b.text() === 'Cancel')
    await cancelBtn.trigger('click')
    await flushPromises()
    expect(reorderList).not.toHaveBeenCalled()
  })
})
