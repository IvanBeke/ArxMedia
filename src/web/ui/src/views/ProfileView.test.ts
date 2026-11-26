import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { authAPI } from '@/api'
import { mockStatsAPI, ratingStats } from '@/test-support/stats'
import ProfileView from '@/views/ProfileView.vue'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type { User, UserProfile } from '@/types/api'

const viewer: User = { id: 1, username: 'alex', email: '', bio: '', avatar: null, location: '', website: '', preferred_region: 'US', language: 'en', account_visibility: 'public', followers_count: 0, following_count: 0, is_staff: false, integrations: { radarr: false, sonarr: false, jellyfin: false }, created_at: '' }

let api: ReturnType<typeof mockStatsAPI>

function profile(isFollowing: boolean): UserProfile {
  return {
    ...viewer,
    id: 2,
    username: 'bob',
    permissions: { can_view_activity: true, can_view_lists: true },
    recent_activity: [],
    visible_lists: [{ id: 7, name: 'Favourites', description: '', item_count: 3 }],
    viewer_relationship: { follows_you: false, is_friend: false, is_self: false, is_following: isFollowing },
  }
}

async function mountView(isFollowing = false, profileOverrides: Partial<UserProfile> = {}) {
  vi.spyOn(authAPI, 'getUser').mockResolvedValue({ ...profile(isFollowing), ...profileOverrides })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/profile/:username', component: ProfileView },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
  })
  await router.push('/profile/bob')
  await router.isReady()
  const wrapper = mount(ProfileView, {
    global: { plugins: [router], stubs: { ActivityHeatmap: true, HistoryMediaCard: true } },
  })
  await flushPromises()
  return wrapper
}

async function openListsTab(wrapper: Awaited<ReturnType<typeof mountView>>) {
  await wrapper.findAll('nav button').at(1)?.trigger('click')
}

describe('ProfileView translations', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    api = mockStatsAPI()
    localStorage.clear()
    setActivePinia(createPinia())
    useAuthStore().user = viewer
  })

  it('shows the stat summary, follow button and list card text in English', async () => {
    const wrapper = await mountView()
    const labels = wrapper.findAll('.card p.text-xs').map((label) => label.text())

    expect(labels).toEqual(['Movies Watched', 'Episodes Watched', 'Watch time', 'Avg. Rating'])
    expect(wrapper.text()).toContain('2h 30m')
    expect(wrapper.find('button.btn-primary').text()).toBe('Follow')

    await openListsTab(wrapper)
    expect(wrapper.text()).toContain('No description')
    expect(wrapper.text()).toContain('3 items')
  })

  it('shows the unfollow button when already following', async () => {
    const wrapper = await mountView(true)

    expect(wrapper.find('button.btn-primary').text()).toBe('Unfollow')
  })

  it('translates the stat summary, follow button and list card text to Spanish', async () => {
    usePreferencesStore().setLocale('es')
    const wrapper = await mountView()
    const labels = wrapper.findAll('.card p.text-xs').map((label) => label.text())

    expect(labels).toEqual(['Películas vistas', 'Episodios vistos', 'Tiempo visto', 'Nota media'])
    expect(wrapper.find('button.btn-primary').text()).toBe('Seguir')

    await openListsTab(wrapper)
    expect(wrapper.text()).toContain('Sin descripción')
    expect(wrapper.text()).toContain('3 elementos')
  })

  it('links the Stats title to the stats page', async () => {
    const wrapper = await mountView()

    const link = wrapper.get('a[href="/profile/bob/stats"]')
    expect(link.text()).toBe('Stats')
    expect(api.watchCount).toHaveBeenCalledWith('bob')
    expect(api.watchTime).toHaveBeenCalledWith('bob')
    expect(api.ratings).toHaveBeenCalledWith('bob')
  })

  it('only requests the stats the summary shows', async () => {
    await mountView()

    expect(api.library).not.toHaveBeenCalled()
    expect(api.monthly).not.toHaveBeenCalled()
    expect(api.habits).not.toHaveBeenCalled()
  })

  it('shows an error with retry when the stats fail to load', async () => {
    api.ratings.mockRejectedValueOnce({ status: 500 })

    const wrapper = await mountView()
    expect(wrapper.get('[role="alert"]').text()).toContain('Could not load stats.')

    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(api.ratings).toHaveBeenCalledTimes(2)
    expect(api.watchCount).toHaveBeenCalledTimes(1)
    expect(api.watchTime).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('2h 30m')
  })

  it('hides the stats section when the profile content is locked', async () => {
    const wrapper = await mountView(false, { permissions: { can_view_activity: false, can_view_lists: false } })

    expect(api.watchCount).not.toHaveBeenCalled()
    expect(api.watchTime).not.toHaveBeenCalled()
    expect(api.ratings).not.toHaveBeenCalled()
    expect(wrapper.find('a[href="/profile/bob/stats"]').exists()).toBe(false)
  })

  it('translates the unfollow button to Spanish', async () => {
    usePreferencesStore().setLocale('es')
    const wrapper = await mountView(true)

    expect(wrapper.find('button.btn-primary').text()).toBe('Dejar de seguir')
  })
})
