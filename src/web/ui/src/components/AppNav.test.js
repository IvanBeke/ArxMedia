import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppNav from '@/components/AppNav.vue'
import { useAuthStore } from '@/stores/auth'

function mountAppNav() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })

  return mount(AppNav, {
    global: {
      plugins: [router],
      stubs: {
        SearchBar: true,
        Transition: false,
      },
    },
  })
}

describe('AppNav', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps the mobile and desktop navigation breakpoints aligned', () => {
    const wrapper = mountAppNav()
    const desktopNav = wrapper.find('.hidden.lg\\:flex')
    const mobileMenuButton = wrapper.find('button[aria-haspopup="menu"]')

    expect(desktopNav.exists()).toBe(true)
    expect(mobileMenuButton.classes()).toContain('lg:hidden')
  })

  it('opens the complete authenticated mobile navigation and closes after selection', async () => {
    const auth = useAuthStore()
    auth.user = { username: 'alex' }
    const wrapper = mountAppNav()

    await wrapper.find('button[aria-label="Open navigation menu"]').trigger('click')

    expect(wrapper.find('.mobile-nav-link').exists()).toBe(true)
    expect(wrapper.findAll('.mobile-nav-link').map((link) => link.text())).toEqual([
      'Discover',
      'My Shows',
      'My Movies',
      'History',
      'Watchlist',
      'Calendar',
      'Data',
      'Settings',
      'Profile',
      'Sign Out',
    ])

    await wrapper.findAll('a[href="/watchlist"]').at(-1).trigger('click')
    expect(wrapper.vm.showMobileMenu).toBe(false)
  })

  it('logs out and returns to the home view', async () => {
    const auth = useAuthStore()
    auth.user = { username: 'alex' }
    const wrapper = mountAppNav()

    await wrapper.find('button[aria-label="Open navigation menu"]').trigger('click')
    await wrapper.findAll('.mobile-nav-link').at(-1).trigger('click')
    await wrapper.vm.$router.isReady()

    expect(auth.user).toBe(null)
    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/')
  })
})
