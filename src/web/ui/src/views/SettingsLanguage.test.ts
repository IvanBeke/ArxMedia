import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { authAPI } from '@/api'
import SettingsView from '@/views/SettingsView.vue'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type { User } from '@/types/api'

const user: User = { id: 1, username: 'alex', email: 'alex@example.com', bio: '', avatar: null, location: '', website: '', preferred_region: 'US', language: 'en', account_visibility: 'public', followers_count: 0, following_count: 0, total_watched_movies: 0, total_watched_episodes: 0, is_staff: false, integrations: { radarr: false, sonarr: false, jellyfin: false }, created_at: '' }

async function mountView() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { AvatarUpload: true } } })
  await flushPromises()
  return wrapper
}

function languageSelect(wrapper: Awaited<ReturnType<typeof mountView>>) {
  const select = wrapper.findAll('select').find((candidate) => candidate.findAll('option').some((option) => option.element.value === 'es'))
  if (!select) throw new Error('language select not found')
  return select
}

describe('SettingsView language', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
    vi.spyOn(authAPI, 'me').mockResolvedValue(user)
  })

  it('saves the language on the account and switches the UI', async () => {
    const updateProfile = vi.spyOn(authAPI, 'updateProfile').mockResolvedValue({ ...user, language: 'es' })
    const wrapper = await mountView()

    await languageSelect(wrapper).setValue('es')
    await flushPromises()

    expect(updateProfile).toHaveBeenCalledWith({ language: 'es' })
    expect(usePreferencesStore().locale).toBe('es')
    expect(useAuthStore().user?.language).toBe('es')
  })

  it('keeps the current language and shows an error when saving fails', async () => {
    vi.spyOn(authAPI, 'updateProfile').mockRejectedValue({})
    const wrapper = await mountView()

    await languageSelect(wrapper).setValue('es')
    await flushPromises()

    expect(usePreferencesStore().locale).toBe('en')
    expect((languageSelect(wrapper).element as HTMLSelectElement).value).toBe('en')
    expect(wrapper.text()).toContain('Failed to update language')
  })
})
