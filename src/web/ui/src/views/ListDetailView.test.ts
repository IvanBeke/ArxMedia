import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import type { DOMWrapper, VueWrapper } from '@vue/test-utils'
import ListDetailView from '@/views/ListDetailView.vue'

interface TestListItem {
  id: number
  media_type: 'movie'
  tmdb_id: number
  custom_order?: number
  title?: string
}

interface ListDetailViewModel {
  collaboratorResults: { id: number; username: string }[]
  showCollaboratorResults: boolean
  hasReordered: boolean
  items: TestListItem[]
  drag: unknown
  reorderDisplayItems: TestListItem[]
  $nextTick(): Promise<void>
}

function viewModel(wrapper: VueWrapper): ListDetailViewModel {
  return wrapper.vm as unknown as ListDetailViewModel
}

function requiredButton(wrapper: VueWrapper, text: string, exact = false): DOMWrapper<HTMLButtonElement> {
  const button = wrapper.findAll<HTMLButtonElement>('button').find((candidate) => exact ? candidate.text() === text : candidate.text().includes(text))
  if (!button) throw new Error(`Could not find button containing ${text}`)
  return button
}

function setRect(element: Element, left: number, top: number, width = 100, height = 160) {
  element.getBoundingClientRect = () => new DOMRect(left, top, width, height)
}

interface DragCoordinates {
  clientX: number
  clientY: number
}

interface DragData {
  id: number
  [key: symbol]: unknown
}

interface DropTargetRegistration {
  element: HTMLElement
  getData: (args: { input: DragCoordinates; element: HTMLElement }) => DragData
}

interface MonitorRegistration {
  onDragStart: (args: { source: { data: DragData } }) => void
  onDrag: (args: { location: { current: { input: DragCoordinates; dropTargets: Array<{ data: DragData }> } } }) => void
  onDrop: () => void
}

const dnd = vi.hoisted(() => ({
  dropTargets: [] as DropTargetRegistration[],
  monitor: null as MonitorRegistration | null,
}))

vi.mock('@atlaskit/pragmatic-drag-and-drop/element/adapter', () => ({
  draggable: () => () => undefined,
  dropTargetForElements: (registration: DropTargetRegistration) => {
    dnd.dropTargets.push(registration)
    return () => undefined
  },
  monitorForElements: (registration: MonitorRegistration) => {
    dnd.monitor = registration
    return () => undefined
  },
}))

function requiredMonitor(): MonitorRegistration {
  if (!dnd.monitor) throw new Error('Reorder monitor was not registered')
  return dnd.monitor
}

function targetData(id: string, coordinates: DragCoordinates): DragData {
  const target = dnd.dropTargets.find((registration) => registration.element.dataset.reorderId === id)
  if (!target) throw new Error(`Reorder target ${id} was not registered`)
  return target.getData({ input: coordinates, element: target.element })
}

function startDrag(id: number): void {
  requiredMonitor().onDragStart({ source: { data: { id } } })
}

function dragOver(id: string, coordinates: DragCoordinates): void {
  requiredMonitor().onDrag({
    location: { current: { input: coordinates, dropTargets: [{ data: targetData(id, coordinates) }] } },
  })
}

function drop(): void {
  requiredMonitor().onDrop()
}

const mountedWrappers: VueWrapper[] = []

const { getList, getListItems, reorderList, updateList } = vi.hoisted(() => ({
  getList: vi.fn(),
  getListItems: vi.fn(),
  reorderList: vi.fn(),
  updateList: vi.fn(),
}))

vi.mock('@/api', () => {
  return {
    trackingAPI: {
      getList,
      getListItems,
      reorderList,
      updateList,
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

function paged(items: TestListItem[]) {
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
    attachTo: document.body,
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
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('ListDetailView custom_order', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    dnd.dropTargets = []
    dnd.monitor = null
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

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('defaults to custom_order sorting', async () => {
    const wrapper = await mountView()
    // MediaFilterBar should be initialized with custom_order
    expect(getListItems).toHaveBeenCalledWith('1', expect.objectContaining({ sort: 'custom_order', direction: 'asc' }))
    expect(wrapper.text()).not.toContain('Could not load')
  })

  it('defers collaborator changes until the list is saved', async () => {
    const wrapper = await mountView()
    const editButton = requiredButton(wrapper, 'Edit', true)
    await editButton.trigger('click')

    const vm = viewModel(wrapper)
    vm.collaboratorResults = [{ id: 2, username: 'collaborator' }]
    vm.showCollaboratorResults = true
    await vm.$nextTick()

    const resultButton = requiredButton(wrapper, 'collaborator', true)
    await resultButton.trigger('click')
    const existingCollaborator = requiredButton(wrapper, 'x', true)
    await existingCollaborator.trigger('click')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(updateList).toHaveBeenCalledWith('1', expect.objectContaining({ collaborator_ids: [2] }))
  })

  it('allows reorder anytime when canEdit', async () => {
    const wrapper = await mountView()
    await flushPromises()
    const reorderBtn = requiredButton(wrapper, 'Reorder')
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
    const reorderBtn = requiredButton(wrapper, 'Reorder')
    await reorderBtn.trigger('click')
    await flushPromises()
    expect(getListItems).toHaveBeenCalledWith('1', expect.objectContaining({ sort: 'custom_order', direction: 'asc', page: 1 }))
    // Simulate drag: move first to last via component method
    // Directly test that Done triggers single reorder call
    const vm = viewModel(wrapper)
    // items are already loaded, simulate hasReordered
    vm.hasReordered = true
    vm.items = [
      { id: 12, media_type: 'movie', tmdb_id: 103, custom_order: 2 },
      { id: 11, media_type: 'movie', tmdb_id: 102, custom_order: 1 },
      { id: 10, media_type: 'movie', tmdb_id: 101, custom_order: 0 },
    ]
    const doneBtn = requiredButton(wrapper, 'Done', true)
    await doneBtn.trigger('click')
    await flushPromises()
    expect(reorderList).toHaveBeenCalledTimes(1)
    expect(reorderList).toHaveBeenCalledWith('1', [12, 11, 10])
  })

  it('moves a lifted card while the pointer is dragged', async () => {
    const wrapper = await mountView()
    const reorderBtn = requiredButton(wrapper, 'Reorder')
    await reorderBtn.trigger('click')
    await flushPromises()

    const cards = wrapper.findAll('[data-reorder-id]')
    const sourceCard = cards.find((card) => card.attributes('data-reorder-id') === '10')
    if (!sourceCard) throw new Error('Source reorder card was not rendered')
    cards.forEach((card, index) => {
      setRect(card.element, index * 120, 0)
    })
    const handle = sourceCard.find('.reorder-handle')
    setRect(handle.element, 0, 0)

    startDrag(10)
    const vm = viewModel(wrapper)
    await vm.$nextTick()
    expect(wrapper.find('.drag-preview').exists()).toBe(true)

    dragOver('12', { clientX: 250, clientY: 150 })
    await vm.$nextTick()
    expect(vm.drag).toBeTruthy()
    expect(vm.reorderDisplayItems.map((item) => item.id)).toEqual([11, 12, 10])

    drop()
    await vm.$nextTick()
    expect(wrapper.find('.drag-preview').exists()).toBe(false)
    expect(vm.items.map((item) => item.id)).toEqual([11, 12, 10])
  })

  it('keeps row changes ordered by the pointer position within the target row', async () => {
    const wrapper = await mountView()
    const reorderBtn = requiredButton(wrapper, 'Reorder')
    await reorderBtn.trigger('click')
    await flushPromises()

    const vm = viewModel(wrapper)
    vm.items = [
      { id: 10, media_type: 'movie', tmdb_id: 101 },
      { id: 11, media_type: 'movie', tmdb_id: 102 },
      { id: 12, media_type: 'movie', tmdb_id: 103 },
      { id: 13, media_type: 'movie', tmdb_id: 104 },
      { id: 14, media_type: 'movie', tmdb_id: 105 },
      { id: 15, media_type: 'movie', tmdb_id: 106 },
    ]
    await vm.$nextTick()
    const cards = wrapper.findAll('[data-reorder-id]')
    cards.forEach((card, index) => {
      const row = index < 2 ? 0 : 180
      const column = index % 2
      setRect(card.element, column * 120, row)
    })
    const firstCard = cards[0]
    if (!firstCard) throw new Error('First reorder card was not rendered')
    const handle = firstCard.find('.reorder-handle')
    setRect(handle.element, 0, 0)

    startDrag(10)
    await vm.$nextTick()

    dragOver('12', { clientX: 20, clientY: 220 })
    await vm.$nextTick()

    expect(vm.reorderDisplayItems.map((item) => item.id)).toEqual([11, 10, 12, 13, 14, 15])
    drop()
    await vm.$nextTick()
    expect(vm.items.map((item) => item.id)).toEqual([11, 10, 12, 13, 14, 15])
  })

  it('can jump over more than one row', async () => {
    const wrapper = await mountView()
    const reorderBtn = requiredButton(wrapper, 'Reorder')
    await reorderBtn.trigger('click')
    await flushPromises()

    const cards = wrapper.findAll('[data-reorder-id]')
    cards.forEach((card, index) => {
      const row = Math.floor(index / 2) * 180
      const column = index % 2
      setRect(card.element, column * 120, row)
    })
    const firstCard = cards[0]
    if (!firstCard) throw new Error('First reorder card was not rendered')
    const handle = firstCard.find('.reorder-handle')
    setRect(handle.element, 0, 0)

    startDrag(10)
    const vm = viewModel(wrapper)
    await vm.$nextTick()

    dragOver('12', { clientX: 20, clientY: 400 })
    await vm.$nextTick()

    expect(vm.reorderDisplayItems.map((item) => item.id)).toEqual([11, 12, 10])
    drop()
    await vm.$nextTick()
    expect(vm.items.map((item) => item.id)).toEqual([11, 12, 10])
  })

  it('Cancel discards without saving', async () => {
    const wrapper = await mountView()
    await flushPromises()
    const reorderBtn = requiredButton(wrapper, 'Reorder')
    await reorderBtn.trigger('click')
    await flushPromises()
    const vm = viewModel(wrapper)
    vm.hasReordered = true
    vm.items = [
      { id: 12, media_type: 'movie', tmdb_id: 103 },
      { id: 10, media_type: 'movie', tmdb_id: 101 },
    ]
    const cancelBtn = requiredButton(wrapper, 'Cancel', true)
    await cancelBtn.trigger('click')
    await flushPromises()
    expect(reorderList).not.toHaveBeenCalled()
  })
})
