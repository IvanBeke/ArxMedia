import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import RadarrAction from '@/components/RadarrAction.vue'
import AddToRadarrDialog from '@/components/AddToRadarrDialog.vue'

const { getRadarrMovie, getRadarrOptions, addRadarrMovie, removeRadarrMovie } = vi.hoisted(() => ({
  getRadarrMovie: vi.fn(),
  getRadarrOptions: vi.fn(),
  addRadarrMovie: vi.fn(),
  removeRadarrMovie: vi.fn(),
}))

vi.mock('@/api', () => ({ integrationsAPI: { getRadarrMovie, getRadarrOptions, addRadarrMovie, removeRadarrMovie } }))

const RADARR_URL = 'https://radarr.example.com/movie/the-matrix-603'

async function mountAction() {
  const wrapper = mount(RadarrAction, { props: { tmdbId: 603, title: 'The Matrix' } })
  await flushPromises()
  return wrapper
}

function actionButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('.inline-flex')
}

function buttonText(wrapper: ReturnType<typeof mount>) {
  return actionButton(wrapper).text()
}

describe('RadarrAction', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getRadarrMovie.mockResolvedValue({ added: false })
    getRadarrOptions.mockResolvedValue({
      root_folders: [{ path: '/movies', free_space: null }],
      quality_profiles: [{ id: 4, name: 'HD-1080p' }],
      tags: [],
    })
    addRadarrMovie.mockResolvedValue({ added: true, url: RADARR_URL })
  })

  it('offers to add a movie that is not in Radarr yet', async () => {
    const wrapper = await mountAction()

    expect(getRadarrMovie).toHaveBeenCalledWith(603, expect.any(Object))
    expect(buttonText(wrapper)).toBe('Add to Radarr')
  })

  it('shows "In Radarr" when the movie is already added', async () => {
    getRadarrMovie.mockResolvedValue({ added: true, path: '/movies/The Matrix (1999)', monitored: true, url: RADARR_URL })

    const wrapper = await mountAction()

    expect(buttonText(wrapper)).toBe('In Radarr')
  })

  it('keeps "In Radarr" as a button that opens the dialog', async () => {
    getRadarrMovie.mockResolvedValue({ added: true, path: '/movies/The Matrix (1999)', monitored: true, url: RADARR_URL })

    const wrapper = await mountAction()

    expect(actionButton(wrapper).element.tagName).toBe('BUTTON')
    expect(actionButton(wrapper).attributes('href')).toBeUndefined()
    await actionButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('hides the button until the state is known', async () => {
    getRadarrMovie.mockReturnValue(new Promise(() => {}))

    const wrapper = await mountAction()

    expect(actionButton(wrapper).exists()).toBe(false)
  })

  it('falls back to "Add to Radarr" when the state cannot be loaded', async () => {
    getRadarrMovie.mockRejectedValue({ detail: 'Could not reach Radarr.', status: 502 })

    const wrapper = await mountAction()

    expect(buttonText(wrapper)).toBe('Add to Radarr')
  })

  it('opens the dialog from the button', async () => {
    const wrapper = await mountAction()

    await actionButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('switches to "In Radarr" and emits added after a successful add', async () => {
    addRadarrMovie.mockResolvedValue({ added: true, path: '/movies/The Matrix (1999)', monitored: true, url: RADARR_URL })
    const wrapper = await mountAction()
    await actionButton(wrapper).trigger('click')
    await flushPromises()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('added')).toHaveLength(1)
    expect(buttonText(wrapper)).toBe('In Radarr')
  })

  it('goes back to "Add to Radarr" and emits removed after the movie is removed', async () => {
    getRadarrMovie.mockResolvedValue({ added: true, path: '/movies/The Matrix (1999)', monitored: true, url: RADARR_URL })
    removeRadarrMovie.mockResolvedValue({ added: false })
    const wrapper = await mountAction()
    await actionButton(wrapper).trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'Remove from Radarr')!.trigger('click')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('removed')).toHaveLength(1)
    expect(buttonText(wrapper)).toBe('Add to Radarr')
  })

  it('reflects an already-added state discovered by the dialog', async () => {
    const wrapper = await mountAction()

    wrapper.findComponent(AddToRadarrDialog).vm.$emit('synced', { added: true, url: RADARR_URL })
    await flushPromises()

    expect(buttonText(wrapper)).toBe('In Radarr')
  })
})
