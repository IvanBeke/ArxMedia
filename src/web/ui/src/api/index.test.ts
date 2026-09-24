import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { authAPI } from '@/api'

function response(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response
}

describe('API token refresh', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('stores the rotated refresh token before retrying the request', async () => {
    localStorage.setItem('access_token', 'expired-access-token')
    localStorage.setItem('refresh_token', 'current-refresh-token')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ detail: 'Token is invalid or expired.' }, 401))
      .mockResolvedValueOnce(response({ access: 'new-access-token', refresh: 'rotated-refresh-token' }))
      .mockResolvedValueOnce(response({ id: 1, username: 'testuser' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(authAPI.me()).resolves.toEqual({ id: 1, username: 'testuser' })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/auth/token/refresh/')
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ refresh: 'current-refresh-token' }),
    })
    expect(localStorage.getItem('access_token')).toBe('new-access-token')
    expect(localStorage.getItem('refresh_token')).toBe('rotated-refresh-token')
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      headers: { Authorization: 'Bearer new-access-token' },
    })
  })
})
