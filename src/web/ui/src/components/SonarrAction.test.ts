import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import SonarrAction from '@/components/SonarrAction.vue'
import AddToSonarrDialog from '@/components/AddToSonarrDialog.vue'
import { INTEGRATION_BRANDS } from '@/constants/integrations'

const { getSonarrSeries, getSonarrOptions, addSonarrSeries, removeSonarrSeries } = vi.hoisted(() => ({
  getSonarrSeries: vi.fn(),
  getSonarrOptions: vi.fn(),
  addSonarrSeries: vi.fn(),
  removeSonarrSeries: vi.fn(),
}))

vi.mock('@/api', () => ({ integrationsAPI: { getSonarrSeries, getSonarrOptions, addSonarrSeries, removeSonarrSeries } }))

const SONARR_URL = 'https://sonarr.example.com/series/breaking-bad'

async function mountAction() {
  const wrapper = mount(SonarrAction, { props: { tmdbId: 1396, title: 'Breaking Bad' } })
  await flushPromises()
  return wrapper
}

function actionButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('.inline-flex')
}

function buttonText(wrapper: ReturnType<typeof mount>) {
  return actionButton(wrapper).text()
}

describe('SonarrAction', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getSonarrSeries.mockResolvedValue({ added: false })
    getSonarrOptions.mockResolvedValue({
      root_folders: [{ path: '/tv', free_space: null }],
      quality_profiles: [{ id: 4, name: 'HD-1080p' }],
      tags: [],
    })
    addSonarrSeries.mockResolvedValue({ added: true, url: SONARR_URL })
  })

  it('offers to add a show that is not in Sonarr yet', async () => {
    const wrapper = await mountAction()

    expect(getSonarrSeries).toHaveBeenCalledWith(1396, expect.any(Object))
    expect(buttonText(wrapper)).toBe('Add to Sonarr')
  })

  it('shows the Sonarr icon after the name, in the Sonarr colour', async () => {
    const wrapper = await mountAction()

    expect(wrapper.get('img').attributes('src')).toBe(INTEGRATION_BRANDS.sonarr.icon)
    expect(actionButton(wrapper).classes()).toContain('text-sonarr')
  })

  it('shows "In Sonarr" when the show is already added', async () => {
    getSonarrSeries.mockResolvedValue({ added: true, path: '/tv/Breaking Bad', monitored: true, url: SONARR_URL })

    const wrapper = await mountAction()

    expect(buttonText(wrapper)).toBe('In Sonarr')
  })

  it('keeps "In Sonarr" as a button that opens the dialog', async () => {
    getSonarrSeries.mockResolvedValue({ added: true, path: '/tv/Breaking Bad', monitored: true, url: SONARR_URL })

    const wrapper = await mountAction()

    expect(actionButton(wrapper).element.tagName).toBe('BUTTON')
    await actionButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('hides the button until the state is known', async () => {
    getSonarrSeries.mockReturnValue(new Promise(() => {}))

    const wrapper = await mountAction()

    expect(actionButton(wrapper).exists()).toBe(false)
  })

  it('falls back to "Add to Sonarr" when the state cannot be loaded', async () => {
    getSonarrSeries.mockRejectedValue({ detail: 'This show has no TheTVDB id, which Sonarr needs.', status: 422 })

    const wrapper = await mountAction()

    expect(buttonText(wrapper)).toBe('Add to Sonarr')
  })

  it('opens the dialog from the button', async () => {
    const wrapper = await mountAction()

    await actionButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('switches to "In Sonarr" and emits added after a successful add', async () => {
    const wrapper = await mountAction()
    await actionButton(wrapper).trigger('click')
    await flushPromises()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('added')).toHaveLength(1)
    expect(buttonText(wrapper)).toBe('In Sonarr')
  })

  it('goes back to "Add to Sonarr" and emits removed after the show is removed', async () => {
    getSonarrSeries.mockResolvedValue({ added: true, path: '/tv/Breaking Bad', monitored: true, url: SONARR_URL })
    removeSonarrSeries.mockResolvedValue({ added: false })
    const wrapper = await mountAction()
    await actionButton(wrapper).trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'Remove from Sonarr')!.trigger('click')

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('removed')).toHaveLength(1)
    expect(buttonText(wrapper)).toBe('Add to Sonarr')
  })

  it('reflects an already-added state discovered by the dialog', async () => {
    const wrapper = await mountAction()

    wrapper.findComponent(AddToSonarrDialog).vm.$emit('synced', { added: true, url: SONARR_URL })
    await flushPromises()

    expect(buttonText(wrapper)).toBe('In Sonarr')
  })
})
