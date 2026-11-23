import { describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { useDetailTabs } from '@/composables/useDetailTabs'

const Detail = defineComponent({
  setup() {
    return useDetailTabs(['overview', 'cast', 'more'] as const, () => [
      { id: 'overview', label: 'Overview' },
      { id: 'cast', label: 'Cast' },
    ])
  },
  template: '<div />',
})

async function mountDetail(initial: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/movies/:id', component: Detail },
      { path: '/dashboard', component: { template: '<div />' } },
    ],
  })
  await router.push(initial)
  await router.isReady()
  const wrapper = mount(Detail, { global: { plugins: [router] } })
  return { router, wrapper }
}

describe('useDetailTabs', () => {
  it('pushes the selected tab to the URL and follows back/forward', async () => {
    const { router, wrapper } = await mountDetail('/movies/1')

    wrapper.vm.activeTab = 'cast'
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/movies/1?tab=cast')

    router.back()
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/movies/1')
    expect(wrapper.vm.activeTab).toBe('overview')

    router.forward()
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/movies/1?tab=cast')
    expect(wrapper.vm.activeTab).toBe('cast')
  })

  it('shows the default for an unavailable tab without touching the URL', async () => {
    const { router, wrapper } = await mountDetail('/movies/1?tab=more')
    const navigations: string[] = []
    router.afterEach((to) => navigations.push(to.fullPath))
    await flushPromises()

    expect(wrapper.vm.activeTab).toBe('overview')
    expect(router.currentRoute.value.fullPath).toBe('/movies/1?tab=more')
    expect(navigations).toEqual([])
  })

  it('leaves the next page URL alone while the page is still mounted', async () => {
    const { router } = await mountDetail('/movies/1?tab=cast')

    await router.push('/dashboard')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/dashboard')
  })
})
