import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { authAPI, mediaAPI } from '@/api'
import SettingsView from '@/views/SettingsView.vue'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type { User, WatchRegion } from '@/types/api'

const user: User = { id: 1, username: 'alex', email: 'alex@example.com', bio: '', avatar: null, location: '', website: '', preferred_region: 'ES', language: 'en', account_visibility: 'public', followers_count: 0, following_count: 0, is_staff: false, integrations: { radarr: false, sonarr: false, jellyfin: false }, created_at: '' }
const regions: WatchRegion[] = [
  { code: 'AR', name: 'Argentina' },
  { code: 'ES', name: 'Spain' },
  { code: 'PE', name: 'Peru' },
]

async function mountView() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { AvatarUpload: true } } })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountView>>

function selectWithOption(wrapper: Wrapper, value: string) {
  const select = wrapper.findAll('select').find((candidate) => candidate.findAll('option').some((option) => option.element.value === value))
  if (!select) throw new Error(`select with option ${value} not found`)
  return select
}

describe('SettingsView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
    vi.spyOn(authAPI, 'me').mockResolvedValue(user)
    vi.spyOn(mediaAPI, 'watchRegions').mockResolvedValue(regions)
  })

  describe('provider region', () => {
    it('lists the regions the API returns by name, keeping the codes as values', async () => {
      const select = selectWithOption(await mountView(), 'PE')
      const options = select.findAll('option')

      expect(options.map((option) => [option.element.value, option.text()])).toEqual([
        ['AR', 'Argentina'],
        ['ES', 'Spain'],
        ['PE', 'Peru'],
      ])
      expect((select.element as HTMLSelectElement).value).toBe('ES')
    })

    it('saves the selected region as its code', async () => {
      const updateProfile = vi.spyOn(authAPI, 'updateProfile').mockResolvedValue({ ...user, preferred_region: 'PE' })
      const wrapper = await mountView()

      await selectWithOption(wrapper, 'PE').setValue('PE')
      await wrapper.find('button.btn-primary').trigger('click')
      await flushPromises()

      expect(updateProfile).toHaveBeenCalledWith(expect.objectContaining({ preferred_region: 'PE' }))
    })

    it('leaves the select empty without breaking the page when the list fails to load', async () => {
      vi.spyOn(mediaAPI, 'watchRegions').mockRejectedValue({ detail: 'Unable to load regions right now.' })

      const wrapper = await mountView()

      expect(wrapper.find('select').findAll('option')).toHaveLength(0)
      expect(wrapper.find('button.btn-primary').exists()).toBe(true)
    })
  })

  describe('language', () => {
    const languageSelect = (wrapper: Wrapper) => selectWithOption(wrapper, 'es')

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
})
