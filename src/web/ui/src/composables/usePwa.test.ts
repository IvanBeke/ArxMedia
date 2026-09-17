import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { usePwa } from '@/composables/usePwa'

type PwaState = ReturnType<typeof usePwa>

const clientHarness = vi.hoisted(() => {
  const listeners = new Map<string, Array<(event: never) => void>>()
  const workbox = {
    register: vi.fn().mockResolvedValue(undefined),
    messageSkipWaiting: vi.fn(),
    addEventListener: vi.fn((type: string, callback: (event: never) => void) => {
      const list = listeners.get(type) ?? []
      list.push(callback)
      listeners.set(type, list)
    }),
  }
  return { listeners, workbox, createWorkbox: vi.fn(() => workbox) }
})

vi.mock('@/pwa/client', () => ({ createWorkbox: clientHarness.createWorkbox }))

function emitWorkbox(type: string, event: Record<string, unknown> = {}): void {
  for (const callback of clientHarness.listeners.get(type) ?? []) callback(event as never)
}

let probed: PwaState | null = null

const Probe = defineComponent({
  setup() {
    probed = usePwa()
    return () => h('div')
  },
})

const mounted: Array<{ unmount: () => void }> = []

function mountProbe(): PwaState {
  const wrapper = mount(Probe)
  mounted.push(wrapper)
  if (!probed) throw new Error('PWA probe did not initialize')
  return probed
}

function fireInstallPrompt(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = new Event('beforeinstallprompt')
  Object.assign(event, {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome }),
  })
  window.dispatchEvent(event)
  return event as Event & { prompt: ReturnType<typeof vi.fn> }
}

let online = true

// jsdom reports a desktop device, so install tests opt into a mobile one.
function stubMobileDevice(): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: () => ({ matches: true }),
  })
}

describe('usePwa', () => {
  beforeEach(() => {
    online = true
    localStorage.clear()
    clientHarness.listeners.clear()
    Object.defineProperty(window.navigator, 'onLine', {
      configurable: true,
      get: () => online,
    })
    vi.clearAllMocks()
  })

  afterEach(() => {
    while (mounted.length) mounted.pop()?.unmount()
    delete (window as unknown as Record<string, unknown>).matchMedia
  })

  it('reflects online state and follows network events', async () => {
    const state = mountProbe()
    expect(state.isOnline.value).toBe(true)

    online = false
    window.dispatchEvent(new Event('offline'))
    await nextTick()
    expect(state.isOnline.value).toBe(false)

    online = true
    window.dispatchEvent(new Event('online'))
    await nextTick()
    expect(state.isOnline.value).toBe(true)
  })

  it('captures the install prompt and installs', async () => {
    stubMobileDevice()
    const state = mountProbe()
    expect(state.canInstall.value).toBe(false)

    const event = fireInstallPrompt()
    await nextTick()
    expect(state.canInstall.value).toBe(true)

    await state.install()
    expect(event.prompt).toHaveBeenCalledTimes(1)
    expect(state.canInstall.value).toBe(false)
  })

  it('persists install dismissal', async () => {
    stubMobileDevice()
    const state = mountProbe()
    fireInstallPrompt()
    await nextTick()
    expect(state.canInstall.value).toBe(true)

    state.dismissInstall()
    await nextTick()
    expect(state.canInstall.value).toBe(false)
    expect(localStorage.getItem('pwa_install_dismissed')).toBe('true')

    fireInstallPrompt()
    await nextTick()
    expect(state.canInstall.value).toBe(false)
  })

  it('withholds the install prompt on desktop devices', async () => {
    const state = mountProbe()
    expect(state.canInstall.value).toBe(false)

    fireInstallPrompt()
    await nextTick()
    expect(state.canInstall.value).toBe(false)
  })

  it('flags updates when the worker waits and skips waiting on update', async () => {
    const state = mountProbe()
    expect(clientHarness.createWorkbox).toHaveBeenCalledTimes(1)
    expect(state.needRefresh.value).toBe(false)

    emitWorkbox('waiting')
    await nextTick()
    expect(state.needRefresh.value).toBe(true)

    state.update()
    expect(clientHarness.workbox.messageSkipWaiting).toHaveBeenCalledTimes(1)
  })

  it('announces offline readiness on first install', async () => {
    const state = mountProbe()

    emitWorkbox('installed', { isUpdate: false })
    await nextTick()
    expect(state.offlineReady.value).toBe(true)
  })

  it('ignores reinstall events for offline readiness', async () => {
    const state = mountProbe()

    emitWorkbox('installed', { isUpdate: true })
    await nextTick()
    expect(state.offlineReady.value).toBe(false)
  })
})
