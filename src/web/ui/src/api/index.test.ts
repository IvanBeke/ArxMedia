import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { authAPI, trackingAPI } from '@/api'

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

describe('API session requests', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=test-csrf-token; path=/'
  })

  afterEach(() => {
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    vi.unstubAllGlobals()
  })

  it('sends the CSRF token on unsafe requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ id: 1, username: 'testuser' }))
    vi.stubGlobal('fetch', fetchMock)

    await authAPI.login({ username: 'testuser', password: 'secret' })

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': 'test-csrf-token', 'Content-Type': 'application/json' },
    })
  })

  it('does not send the CSRF token on safe requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ id: 1, username: 'testuser' }))
    vi.stubGlobal('fetch', fetchMock)

    await authAPI.me()

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: 'GET', headers: {} })
  })

  it('uploads imports as multipart form data through the shared client', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ id: 7 }))
    vi.stubGlobal('fetch', fetchMock)

    await trackingAPI.importData(new File(['{}'], 'export.zip'), 'zip', 'arxmedia')

    const [url, options] = fetchMock.mock.calls[0] ?? []
    expect(String(url)).toContain('/api/tracking/data/import/?data_format=zip&source=arxmedia')
    expect(options.body).toBeInstanceOf(FormData)
    expect(options.headers).toEqual({ 'X-CSRFToken': 'test-csrf-token' })
  })

  it('surfaces auth endpoint 401s without redirecting', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ detail: 'Incorrect username or password.' }, 401)))
    const before = window.location.href

    await expect(authAPI.login({ username: 'x', password: 'y' })).rejects.toMatchObject({ status: 401 })
    expect(window.location.href).toBe(before)
  })

  it('removes a history entry by its full episode key', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ count: 1, results: [{ id: 42, tmdb_id: 7, media_type: 'episode', season_number: 3, episode_number: 9 }] }))
      .mockResolvedValueOnce(response(null, 204))
    vi.stubGlobal('fetch', fetchMock)

    await trackingAPI.removeFromHistory({ media_type: 'episode', tmdb_id: 7, season_number: 3, episode_number: 9 })

    const lookup = new URL(String(fetchMock.mock.calls[0]?.[0]))
    expect(Object.fromEntries(lookup.searchParams)).toEqual({ tmdb_id: '7', media_type: 'episode', season_number: '3', episode_number: '9' })
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/tracking/history/42/')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: 'DELETE' })
  })

  it('passes an abort signal through to fetch', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ count: 0, results: [] }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await trackingAPI.getMyMovies({ page: 1 }, { signal: controller.signal })

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ signal: controller.signal })
  })
})

