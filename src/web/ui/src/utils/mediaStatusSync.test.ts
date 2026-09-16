import { describe, expect, it } from 'vitest'
import { applyStatusChanged, sortMediaByReleaseDate, type StatusSyncItem } from '@/utils/mediaStatusSync'
import { MEDIA_TYPE } from '@/constants/tracking'

describe('applyStatusChanged', () => {
  it('patches the matching entry by tmdb id', () => {
    const items: StatusSyncItem[] = [
      { id: 1, media_type: MEDIA_TYPE.MOVIE, user_status: { status: 'none' as const } },
      { id: 2, media_type: MEDIA_TYPE.MOVIE, user_status: { status: 'none' as const } },
    ]
    const updated = applyStatusChanged(items, {
      tmdb_id: 2,
      media_type: MEDIA_TYPE.MOVIE,
      status: 'plan_to_watch',
      watched_at: null,
      status_changed_at: '2026-01-01T00:00:00Z',
    })
    expect(updated).toBe(true)
    expect(items[0]?.user_status?.status).toBe('none')
    expect(items[1]?.user_status?.status).toBe('plan_to_watch')
  })

  it('matches collection parts that only carry an id', () => {
    const items: StatusSyncItem[] = [{ id: 550, release_date: '1999-10-15' }]
    const updated = applyStatusChanged(items, {
      tmdb_id: 550,
      media_type: MEDIA_TYPE.MOVIE,
      status: 'watched',
      watched_at: '2026-01-02T00:00:00Z',
      status_changed_at: '2026-01-02T00:00:00Z',
    })
    expect(updated).toBe(true)
    expect(items[0]?.user_status?.status).toBe('watched')
  })

  it('ignores non-matching payloads', () => {
    const items: StatusSyncItem[] = [{ id: 1, media_type: MEDIA_TYPE.MOVIE }]
    expect(
      applyStatusChanged(items, {
        tmdb_id: 999,
        media_type: MEDIA_TYPE.MOVIE,
        status: 'watched',
        watched_at: null,
        status_changed_at: null,
      }),
    ).toBe(false)
    expect(items[0]?.user_status).toBeUndefined()
  })
})

describe('sortMediaByReleaseDate', () => {
  it('sorts chronologically with undated items last', () => {
    const items = [
      { id: 1, release_date: '2001-05-19' },
      { id: 2, release_date: '1977-05-25' },
      { id: 3, release_date: null },
      { id: 4, release_date: '1980-05-21' },
    ]
    expect(sortMediaByReleaseDate(items).map((item) => item.id)).toEqual([2, 4, 1, 3])
  })
})
