import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { authAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type { User } from '@/types/api'

const user: User = { id: 1, username: 'alex', email: '', bio: '', avatar: null, location: '', website: '', preferred_region: 'US', language: 'es', account_visibility: 'public', followers_count: 0, following_count: 0, is_staff: false, integrations: { radarr: false, sonarr: false, jellyfin: false }, created_at: '' }

describe('auth store language', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('takes the UI language from the account after fetching the current user', async () => {
    vi.spyOn(authAPI, 'me').mockResolvedValue(user)

    await useAuthStore().fetchMe()

    expect(usePreferencesStore().locale).toBe('es')
  })

  it('lets the account language override the stored browser language on login', async () => {
    usePreferencesStore().setLocale('en')
    vi.spyOn(authAPI, 'login').mockResolvedValue(user)

    await useAuthStore().login({ username: 'alex', password: 'secret' })

    expect(usePreferencesStore().locale).toBe('es')
    expect(localStorage.getItem('locale')).toBe('es')
  })

  it('creates the account in the language the guest was browsing in', async () => {
    usePreferencesStore().setLocale('es')
    const register = vi.spyOn(authAPI, 'register').mockResolvedValue(user)

    await useAuthStore().register({ username: 'alex', email: 'a@b.c', password: 'x', password2: 'x' })

    expect(register).toHaveBeenCalledWith(expect.objectContaining({ language: 'es' }))
  })

  it('shows the login failure in the guest language instead of the server text', async () => {
    usePreferencesStore().setLocale('es')
    vi.spyOn(authAPI, 'login').mockRejectedValue({ detail: 'Incorrect username or password.', status: 401 })
    const auth = useAuthStore()

    await auth.login({ username: 'alex', password: 'wrong' })

    expect(auth.error).toBe('Usuario o contraseña incorrectos.')
  })
})
