import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ListDetailView from '@/views/ListDetailView.vue'

const getList = vi.fn()
const getListItems = vi.fn()
const reorderList = vi.fn()
const updateList = vi.fn()

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    trackingAPI: {
      getList: (...args) => getList(...args),
      getListItems: (...args) => getListItems(...args),
      reorderList: (...args) => reorderList(...args),
       updateList: (...args) => updateList(...args),
      deleteList: vi.fn().mockResolvedValue({}),
      addToList: vi.fn().mockResolvedValue({}),
      removeFromList: vi.fn().mockResolvedValue({}),
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
       collaborator_users: [{ id: 3, username: 'existing' }],
      created_at: new Date().toISOString(),
      item_count: 3,
    })
    getListItems.mockResolvedValue(paged([
      { id: 10, media_type: 'movie', tmdb_id: 101, custom_order: 0, title: 'A' },
      { id: 11, media_type: 'movie', tmdb_id: 102, custom_order: 1, title: 'B' },
      { id: 12, media_type: 'movie', tmdb_id: 103, custom_order: 2, title: 'C' },
    ]))
    reorderList.mockResolvedValue({ ordered: true, custom_order: [12, 11, 10] })
     updateList.mockResolvedValue({})
  })

  it('defaults to custom_order sorting', async () => {
    const wrapper = await mountView()
    // MediaFilterBar should be initialized with custom_order
    expect(getListItems).toHaveBeenCalledWith('1', expect.objectContaining({ sort: 'custom_order', direction: 'asc' }))
    expect(wrapper.text()).not.toContain('Could not load')
  })

  it('defers collaborator changes until the list is saved', async () => {
    const wrapper = await mountView()
    const editButton = wrapper.findAll('button').find((button) => button.text() === 'Edit')
    await editButton.trigger('click')

    wrapper.vm.collaboratorResults = [{ id: 2, username: 'collaborator' }]
    wrapper.vm.showCollaboratorResults = true
    await wrapper.vm.$nextTick()

    const resultButton = wrapper.findAll('button').find((button) => button.text() === 'collaborator')
    await resultButton.trigger('click')
    const existingCollaborator = wrapper.findAll('button').find((button) => button.text() === 'x')
    await existingCollaborator.trigger('click')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(updateList).toHaveBeenCalledWith('1', expect.objectContaining({ collaborator_ids: [2] }))
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

  it('moves a lifted card while the pointer is dragged', async () => {
    const wrapper = await mountView()
    const reorderBtn = wrapper.findAll('button').find((b) => b.text().includes('Reorder'))
    await reorderBtn.trigger('click')
    await flushPromises()

    const cards = wrapper.findAll('[data-reorder-id]')
    const sourceCard = cards.find((card) => card.attributes('data-reorder-id') === '10')
    cards.forEach((card, index) => {
      card.element.getBoundingClientRect = () => ({
        left: index * 120,
        top: 0,
        width: 100,
        height: 160,
        right: index * 120 + 100,
        bottom: 160,
      })
    })
    const handle = sourceCard.find('.reorder-handle')
    handle.element.getBoundingClientRect = () => ({
      left: 0,
      top: 0,
      width: 100,
      height: 160,
      right: 100,
      bottom: 160,
    })

    const pointerDown = new Event('pointerdown', { bubbles: true })
    Object.defineProperties(pointerDown, {
      button: { value: 0 },
      clientX: { value: 20 },
      clientY: { value: 40 },
    })
    handle.element.dispatchEvent(pointerDown)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.drag-preview').exists()).toBe(true)

    const pointerMove = new Event('pointermove')
    Object.defineProperties(pointerMove, {
      clientX: { value: 250 },
      clientY: { value: 40 },
    })
    window.dispatchEvent(pointerMove)
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.drag).toBeTruthy()
    expect(wrapper.vm.reorderDisplayItems.map((item) => item.id)).toEqual([11, 12, 10])

    window.dispatchEvent(new Event('pointerup'))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.drag-preview').exists()).toBe(false)
    expect(wrapper.vm.items.map((item) => item.id)).toEqual([11, 12, 10])
  })

  it('keeps row changes ordered by the pointer position within the target row', async () => {
    const wrapper = await mountView()
    const reorderBtn = wrapper.findAll('button').find((b) => b.text().includes('Reorder'))
    await reorderBtn.trigger('click')
    await flushPromises()

    wrapper.vm.items = [
      { id: 10, media_type: 'movie', tmdb_id: 101 },
      { id: 11, media_type: 'movie', tmdb_id: 102 },
      { id: 12, media_type: 'movie', tmdb_id: 103 },
      { id: 13, media_type: 'movie', tmdb_id: 104 },
      { id: 14, media_type: 'movie', tmdb_id: 105 },
      { id: 15, media_type: 'movie', tmdb_id: 106 },
    ]
    await wrapper.vm.$nextTick()
    const cards = wrapper.findAll('[data-reorder-id]')
    cards.forEach((card, index) => {
      const row = index < 2 ? 0 : 180
      const column = index % 2
      card.element.getBoundingClientRect = () => ({
        left: column * 120,
        top: row,
        width: 100,
        height: 160,
        right: column * 120 + 100,
        bottom: row + 160,
      })
    })
    const handle = cards[0].find('.reorder-handle')
    handle.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 160, right: 100, bottom: 160 })

    const pointerDown = new Event('pointerdown', { bubbles: true })
    Object.defineProperties(pointerDown, { button: { value: 0 }, clientX: { value: 20 }, clientY: { value: 40 } })
    handle.element.dispatchEvent(pointerDown)
    await wrapper.vm.$nextTick()

    const pointerMove = new Event('pointermove')
    Object.defineProperties(pointerMove, { clientX: { value: 20 }, clientY: { value: 220 } })
    window.dispatchEvent(pointerMove)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.reorderDisplayItems.map((item) => item.id)).toEqual([11, 10, 12])
    window.dispatchEvent(new Event('pointerup'))
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.items.map((item) => item.id)).toEqual([11, 10, 12])
  })

  it('can jump over more than one row', async () => {
    const wrapper = await mountView()
    const reorderBtn = wrapper.findAll('button').find((b) => b.text().includes('Reorder'))
    await reorderBtn.trigger('click')
    await flushPromises()

    const cards = wrapper.findAll('[data-reorder-id]')
    cards.forEach((card, index) => {
      const row = Math.floor(index / 2) * 180
      const column = index % 2
      card.element.getBoundingClientRect = () => ({
        left: column * 120,
        top: row,
        width: 100,
        height: 160,
        right: column * 120 + 100,
        bottom: row + 160,
      })
    })
    const handle = cards[0].find('.reorder-handle')
    handle.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 160, right: 100, bottom: 160 })

    const pointerDown = new Event('pointerdown', { bubbles: true })
    Object.defineProperties(pointerDown, { button: { value: 0 }, clientX: { value: 20 }, clientY: { value: 40 } })
    handle.element.dispatchEvent(pointerDown)
    await wrapper.vm.$nextTick()

    const pointerMove = new Event('pointermove')
    Object.defineProperties(pointerMove, { clientX: { value: 20 }, clientY: { value: 400 } })
    window.dispatchEvent(pointerMove)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.reorderDisplayItems.map((item) => item.id)).toEqual([11, 12, 10])
    window.dispatchEvent(new Event('pointerup'))
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.items.map((item) => item.id)).toEqual([11, 12, 10])
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
