import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PwaStatus from '@/components/PwaStatus.vue'

const pwaState = vi.hoisted(() => ({
  needRefresh: { value: false },
  offlineReady: { value: false },
  isOnline: { value: true },
  canInstall: { value: false },
  installedApp: true,
  install: vi.fn(),
  dismissInstall: vi.fn(),
  update: vi.fn(),
}))

vi.mock('@/composables/usePwa', () => ({ usePwa: () => pwaState }))

function mountStatus() {
  setActivePinia(createPinia())
  return mount(PwaStatus, {
    global: {
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  })
}

describe('PwaStatus', () => {
  beforeEach(() => {
    pwaState.needRefresh.value = false
    pwaState.offlineReady.value = false
    pwaState.isOnline.value = true
    pwaState.canInstall.value = false
    pwaState.installedApp = true
    vi.clearAllMocks()
  })

  it('renders nothing actionable when online with no updates', () => {
    const wrapper = mountStatus()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('shows the offline banner when offline', () => {
    pwaState.isOnline.value = false
    const wrapper = mountStatus()

    const banner = wrapper.find('[role="alert"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('offline')
  })

  it('shows the update toast and triggers an update', async () => {
    pwaState.needRefresh.value = true
    const wrapper = mountStatus()

    const toast = wrapper.find('[role="alertdialog"]')
    expect(toast.exists()).toBe(true)

    await toast.findAll('button')[1]?.trigger('click')
    expect(pwaState.update).toHaveBeenCalledTimes(1)
  })

  it('withholds the update toast in browser tabs', () => {
    pwaState.needRefresh.value = true
    pwaState.installedApp = false
    const wrapper = mountStatus()

    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
  })

  it('shows the install banner and handles install and dismiss', async () => {
    pwaState.canInstall.value = true
    const wrapper = mountStatus()

    const banner = wrapper.find('[role="dialog"]')
    expect(banner.exists()).toBe(true)

    await banner.findAll('button')[1]?.trigger('click')
    expect(pwaState.install).toHaveBeenCalledTimes(1)

    await banner.findAll('button')[0]?.trigger('click')
    expect(pwaState.dismissInstall).toHaveBeenCalledTimes(1)
  })

})
