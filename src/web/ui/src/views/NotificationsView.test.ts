import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { notificationsAPI } from '@/api'
import NotificationsView from '@/views/NotificationsView.vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import type { ReleaseNotification, User } from '@/types/api'

const user: User = { id: 1, username: 'alex', email: '', bio: '', avatar: null, location: '', website: '', preferred_region: '', account_visibility: 'public', followers_count: 0, following_count: 0, total_watched_movies: 0, total_watched_episodes: 0, is_staff: false, integrations: { radarr: false, sonarr: false, jellyfin: false }, created_at: '' }

function releaseNotification(overrides: Partial<ReleaseNotification> = {}): ReleaseNotification {
  return {
    id: 1, media_type: 'movie', tmdb_id: 550, season_number: null, created_at: '2026-11-12T00:05:00Z',
    read: false, title: 'Release movie', poster_url: '/movie.jpg', release_date: '2026-11-12', ...overrides,
  }
}

let wrapper: VueWrapper | undefined

function render() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  wrapper = mount(NotificationsView, { global: { plugins: [router] } })
  return wrapper
}

describe('NotificationsView', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    setActivePinia(createPinia())
    useAuthStore().user = user
    vi.spyOn(notificationsAPI, 'list').mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    vi.spyOn(notificationsAPI, 'markRead').mockResolvedValue()
    vi.spyOn(notificationsAPI, 'delete').mockResolvedValue()
  })

  afterEach(() => { wrapper?.unmount() })

  it('renders a loading state then an empty page', async () => {
    let finish!: () => void
    vi.mocked(notificationsAPI.list).mockReturnValueOnce(new Promise((resolve) => {
      finish = () => resolve({ count: 0, next: null, previous: null, results: [] })
    }))
    const view = render()
    await view.vm.$nextTick()
    expect(view.find('.skeleton').exists()).toBe(true)
    finish()
    await flushPromises()
    expect(view.text()).toContain("It's quiet in here")
    expect(document.title).toBe('Notifications · ArxMedia')
  })

  it('shows a retryable list error', async () => {
    vi.mocked(notificationsAPI.list).mockRejectedValueOnce(new Error('offline'))
    const view = render()
    await flushPromises()
    expect(view.find('[role="alert"]').text()).toContain('Notifications could not be loaded')
    await view.find('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(view.text()).toContain("It's quiet in here")
  })

  it('renders the release message, destinations, season poster and actions', async () => {
    vi.mocked(notificationsAPI.list).mockResolvedValue({
      count: 3, next: null, previous: null,
      results: [
        releaseNotification(),
        releaseNotification({ id: 2, media_type: 'tv', tmdb_id: 10, season_number: 1, title: 'Series premiere', read: true }),
        releaseNotification({ id: 3, media_type: 'tv', tmdb_id: 20, season_number: 2, title: 'New season', poster_url: '/season.jpg' }),
      ],
    })
    const view = render()
    await flushPromises()
    expect(view.text()).toContain('Release movie was released on November 12, 2026!')
    expect(view.text()).toContain('New season Season 2 was released on November 12, 2026!')
    expect(view.find('a[href="/movies/550"]').exists()).toBe(true)
    expect(view.find('a[href="/tv/10"]').exists()).toBe(true)
    expect(view.find('a[href="/tv/20/season/2"]').exists()).toBe(true)
    expect(view.find('img[src="/season.jpg"]').exists()).toBe(true)
    expect(view.findAll('.sr-only')).toHaveLength(2)
    expect(view.findAll('button[aria-label="Mark as read"]')).toHaveLength(2)
    expect(view.findAll('button[aria-label="Delete notification"]')).toHaveLength(3)
  })

  it('hides the check and dot after reading, and keeps delete available', async () => {
    vi.mocked(notificationsAPI.list).mockResolvedValue({ count: 1, next: null, previous: null, results: [releaseNotification()] })
    useNotificationsStore().unreadCount = 1
    const view = render()
    await flushPromises()
    await view.find('button[aria-label="Mark as read"]').trigger('click')
    await flushPromises()
    expect(view.find('button[aria-label="Mark as read"]').exists()).toBe(false)
    expect(view.find('.sr-only').exists()).toBe(false)
    expect(view.find('button[aria-label="Delete notification"]').exists()).toBe(true)
    expect(useNotificationsStore().unreadCount).toBe(0)
    expect(notificationsAPI.markRead).toHaveBeenCalledWith(1)
  })

  it('keeps the row and shows an error when a read or delete fails', async () => {
    vi.mocked(notificationsAPI.list).mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [releaseNotification()] })
    vi.mocked(notificationsAPI.markRead).mockRejectedValueOnce(new Error('offline'))
    vi.mocked(notificationsAPI.delete).mockRejectedValueOnce(new Error('offline'))
    const view = render()
    await flushPromises()
    await view.find('button[aria-label="Mark as read"]').trigger('click')
    await flushPromises()
    expect(view.find('[role="alert"]').text()).toContain('could not be updated')
    expect(view.find('.sr-only').exists()).toBe(true)
    expect(view.find('button[aria-label="Mark as read"]').exists()).toBe(true)
    await view.find('button[aria-label="Delete notification"]').trigger('click')
    await flushPromises()
    expect(view.findAll('li')).toHaveLength(1)
    await view.find('button[aria-label="Delete notification"]').trigger('click')
    await flushPromises()
    expect(view.findAll('li')).toHaveLength(0)
    expect(view.text()).toContain("It's quiet in here")
  })

  it('falls back to a placeholder title and no poster when catalog metadata is missing', async () => {
    vi.mocked(notificationsAPI.list).mockResolvedValue({ count: 1, next: null, previous: null, results: [releaseNotification({ title: '', poster_url: null })] })
    const view = render()
    await flushPromises()
    expect(view.find('img').exists()).toBe(false)
    expect(view.text()).toContain('Unavailable title')
  })

  it('refills the page from the next one when every visible row is deleted', async () => {
    vi.mocked(notificationsAPI.list)
      .mockResolvedValueOnce({ count: 2, next: '?page=2', previous: null, results: [releaseNotification()] })
      .mockResolvedValueOnce({ count: 1, next: null, previous: null, results: [releaseNotification({ id: 2, title: 'Next page movie' })] })
    const view = render()
    await flushPromises()
    await view.find('button[aria-label="Delete notification"]').trigger('click')
    await flushPromises()
    expect(view.text()).toContain('Next page movie')
    expect(view.text()).not.toContain("It's quiet in here")
  })

  it('loads the selected page and falls back to the previous one when its last row is deleted', async () => {
    vi.mocked(notificationsAPI.list)
      .mockResolvedValueOnce({ count: 21, next: '?page=2', previous: null, results: [releaseNotification()] })
      .mockResolvedValueOnce({ count: 21, next: null, previous: '?page=1', results: [releaseNotification({ id: 21 })] })
      .mockRejectedValueOnce({ status: 404, detail: 'Invalid page.' })
      .mockResolvedValueOnce({ count: 20, next: null, previous: null, results: [releaseNotification({ title: 'Page one movie' })] })
    const view = render()
    await flushPromises()
    await view.find('[aria-label="Go to next page"]').trigger('click')
    await flushPromises()
    expect(notificationsAPI.list).toHaveBeenNthCalledWith(2, 2, expect.anything())
    await view.find('button[aria-label="Delete notification"]').trigger('click')
    await flushPromises()
    expect(notificationsAPI.list).toHaveBeenCalledTimes(4)
    expect(notificationsAPI.list).toHaveBeenNthCalledWith(3, 2, expect.anything())
    expect(notificationsAPI.list).toHaveBeenNthCalledWith(4, 1, expect.anything())
    expect(view.text()).toContain('Page one movie')
  })
})
