import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { authAPI } from '@/api'
import ProfileView from '@/views/ProfileView.vue'
import { useAuthStore } from '@/stores/auth'
import { usePreferencesStore } from '@/stores/preferences'
import type { User, UserProfile } from '@/types/api'

const viewer: User = { id: 1, username: 'alex', email: '', bio: '', avatar: null, location: '', website: '', preferred_region: 'US', account_visibility: 'public', followers_count: 0, following_count: 0, total_watched_movies: 0, total_watched_episodes: 0, is_staff: false, integrations: { radarr: false, sonarr: false, jellyfin: false }, created_at: '' }

function profile(isFollowing: boolean): UserProfile {
  return {
    ...viewer,
    id: 2,
    username: 'bob',
    permissions: { can_view_activity: true, can_view_lists: true },
    recent_activity: [],
    visible_lists: [{ id: 7, name: 'Favourites', description: '', item_count: 3 }],
    stats: { ratings_count: 4, watchlist_count: 5, average_rating: 8 },
    viewer_relationship: { follows_you: false, is_friend: false, is_self: false, is_following: isFollowing },
  }
}

async function mountView(isFollowing = false) {
  vi.spyOn(authAPI, 'getUser').mockResolvedValue(profile(isFollowing))
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
    localStorage.clear()
    setActivePinia(createPinia())
    useAuthStore().user = viewer
  })

  it('shows the stat labels, follow button and list card text in English', async () => {
    const wrapper = await mountView()
    const labels = wrapper.findAll('.card.text-center p.text-xs').map((label) => label.text())

    expect(labels).toEqual(['Movies', 'Episodes', 'Ratings', 'Watchlist', 'Avg Rating'])
    expect(wrapper.find('button.btn-primary').text()).toBe('Follow')

    await openListsTab(wrapper)
    expect(wrapper.text()).toContain('No description')
    expect(wrapper.text()).toContain('3 items')
  })

  it('shows the unfollow button when already following', async () => {
    const wrapper = await mountView(true)

    expect(wrapper.find('button.btn-primary').text()).toBe('Unfollow')
  })

  it('translates the stat labels, follow button and list card text to Spanish', async () => {
    usePreferencesStore().setLocale('es')
    const wrapper = await mountView()
    const labels = wrapper.findAll('.card.text-center p.text-xs').map((label) => label.text())

    expect(labels).toEqual(['Películas', 'Episodios', 'Valoraciones', 'Pendientes', 'Nota media'])
    expect(wrapper.find('button.btn-primary').text()).toBe('Seguir')

    await openListsTab(wrapper)
    expect(wrapper.text()).toContain('Sin descripción')
    expect(wrapper.text()).toContain('3 elementos')
  })

  it('translates the unfollow button to Spanish', async () => {
    usePreferencesStore().setLocale('es')
    const wrapper = await mountView(true)

    expect(wrapper.find('button.btn-primary').text()).toBe('Dejar de seguir')
  })
})
