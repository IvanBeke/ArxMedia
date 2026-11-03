import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import JellyfinLink from '@/components/JellyfinLink.vue'

const { getJellyfinLinks, getJellyfinMovieLink } = vi.hoisted(() => ({ getJellyfinLinks: vi.fn(), getJellyfinMovieLink: vi.fn() }))

vi.mock('@/api', () => ({ integrationsAPI: { getJellyfinLinks, getJellyfinMovieLink } }))

const LINKS = {
  show_url: 'https://jellyfin.example.com/web/index.html#/details?id=show',
  season_url: 'https://jellyfin.example.com/web/index.html#/details?id=season',
  episode_url: 'https://jellyfin.example.com/web/index.html#/details?id=episode',
}

async function mountLink(props: { scope: 'movie' | 'show' | 'season' | 'episode'; seasonNumber?: number; episodeNumber?: number }) {
  const wrapper = mount(JellyfinLink, { props: { tmdbId: 1396, ...props } })
  await flushPromises()
  return wrapper
}

describe('JellyfinLink', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getJellyfinLinks.mockResolvedValue(LINKS)
  })

  it('links the show to Jellyfin in a new tab, with the Jellyfin icon after the name', async () => {
    const wrapper = await mountLink({ scope: 'show' })

    const link = wrapper.get('a')
    expect(link.text()).toBe('Open in Jellyfin')
    expect(link.attributes('href')).toBe(LINKS.show_url)
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toContain('noopener')
    expect(link.classes()).toContain('text-jellyfin')
    expect(Array.from(link.element.children).map((child) => child.tagName)).toEqual(['SPAN', 'IMG'])
    expect(getJellyfinLinks).toHaveBeenCalledWith(1396, {}, expect.any(Object))
  })

  it('links the movie to Jellyfin using the movie lookup', async () => {
    getJellyfinMovieLink.mockResolvedValue({ url: 'https://jellyfin.example.com/web/index.html#/details?id=movie' })

    const wrapper = await mountLink({ scope: 'movie' })

    expect(wrapper.get('a').attributes('href')).toBe('https://jellyfin.example.com/web/index.html#/details?id=movie')
    expect(getJellyfinMovieLink).toHaveBeenCalledWith(1396, expect.any(Object))
    expect(getJellyfinLinks).not.toHaveBeenCalled()
  })

  it('shows nothing when the movie is not in Jellyfin', async () => {
    getJellyfinMovieLink.mockResolvedValue({ url: null })

    const wrapper = await mountLink({ scope: 'movie' })

    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('asks for the season and links to it', async () => {
    const wrapper = await mountLink({ scope: 'season', seasonNumber: 2 })

    expect(getJellyfinLinks).toHaveBeenCalledWith(1396, { season: 2, episode: undefined }, expect.any(Object))
    expect(wrapper.get('a').attributes('href')).toBe(LINKS.season_url)
  })

  it('asks for the episode and links to it', async () => {
    const wrapper = await mountLink({ scope: 'episode', seasonNumber: 2, episodeNumber: 3 })

    expect(getJellyfinLinks).toHaveBeenCalledWith(1396, { season: 2, episode: 3 }, expect.any(Object))
    expect(wrapper.get('a').attributes('href')).toBe(LINKS.episode_url)
  })

  it('shows nothing when Jellyfin has no page for it', async () => {
    getJellyfinLinks.mockResolvedValue({ show_url: LINKS.show_url, season_url: null, episode_url: null })

    const wrapper = await mountLink({ scope: 'episode', seasonNumber: 2, episodeNumber: 3 })

    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('shows nothing when the request fails', async () => {
    getJellyfinLinks.mockRejectedValue({ detail: 'Jellyfin is not configured.', status: 503 })

    const wrapper = await mountLink({ scope: 'show' })

    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('looks the link up again when the episode changes', async () => {
    const wrapper = await mountLink({ scope: 'episode', seasonNumber: 1, episodeNumber: 1 })

    await wrapper.setProps({ episodeNumber: 2 })
    await flushPromises()

    expect(getJellyfinLinks).toHaveBeenCalledTimes(2)
    expect(getJellyfinLinks).toHaveBeenLastCalledWith(1396, { season: 1, episode: 2 }, expect.any(Object))
  })
})
