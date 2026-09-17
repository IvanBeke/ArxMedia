import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import OfflineView from '@/views/OfflineView.vue'
import router from '@/router'

function mountOffline() {
  setActivePinia(createPinia())
  const testRouter = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/offline', component: OfflineView },
    ],
  })

  return testRouter
    .push('/offline')
    .then(() => testRouter.isReady())
    .then(() => ({
      wrapper: mount(OfflineView, {
        global: { plugins: [testRouter] },
      }),
      testRouter,
    }))
}

describe('OfflineView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('registers the offline route without auth requirements', () => {
    const resolved = router.resolve('/offline')

    expect(resolved.name).toBe('offline')
    expect(resolved.meta.requiresAuth).toBeFalsy()
  })

  it('renders the offline message with a retry action', async () => {
    const { wrapper } = await mountOffline()

    expect(wrapper.text()).toContain('offline')
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('returns home when retrying back online', async () => {
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, value: true })
    const { wrapper, testRouter } = await mountOffline()

    await wrapper.find('button').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(testRouter.currentRoute.value.path).toBe('/')
  })
})
