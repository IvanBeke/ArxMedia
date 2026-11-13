import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import LoginView from '@/views/LoginView.vue'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'

function mountLogin(redirect?: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/dashboard', component: { template: '<div />' } },
      { path: '/watchlist', component: { template: '<div />' } },
    ],
  })

  return router.push({ path: '/login', query: redirect ? { redirect } : {} })
    .then(() => router.isReady())
    .then(() => ({
      router,
      wrapper: mount(LoginView, {
        global: {
          plugins: [router, pinia],
          stubs: { RouterLink: true },
        },
      }),
    }))
}

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('translates the form to Spanish', async () => {
    localStorage.clear()
    usePreferencesStore().setLocale('es')
    const { wrapper } = await mountLogin()

    expect(wrapper.find('h1').text()).toBe('Iniciar sesión')
    expect(wrapper.text()).toContain('Hola de nuevo')
    expect(wrapper.text()).toContain('Nombre de usuario')
    expect(wrapper.text()).toContain('Contraseña')
    expect(wrapper.text()).toContain('¿No tienes cuenta?')
    localStorage.clear()
  })

  it('returns to the protected route after login', async () => {
    const { router, wrapper } = await mountLogin('/watchlist?sort=recent')
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockResolvedValue(true)

    await wrapper.find('button').trigger('click')
    await router.isReady()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(router.currentRoute.value.fullPath).toBe('/watchlist?sort=recent')
  })

  it('does not navigate to an external login redirect', async () => {
    const { router, wrapper } = await mountLogin('//example.com')
    const auth = useAuthStore()
    vi.spyOn(auth, 'login').mockResolvedValue(true)

    await wrapper.find('button').trigger('click')
    await router.isReady()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })
})
