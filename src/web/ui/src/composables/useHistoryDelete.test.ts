import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api', () => ({
  trackingAPI: {
    deleteHistory: vi.fn().mockResolvedValue(undefined),
  },
}))

import { trackingAPI as importedTrackingAPI } from '@/api'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import type { WatchEntry } from '@/types/api'
import { getRemoveHistoryConfirmText, useHistoryDelete } from '@/composables/useHistoryDelete'

const trackingAPI = vi.mocked(importedTrackingAPI)

beforeEach(() => {
  setActivePinia(createPinia())
})

function entry(overrides: Partial<WatchEntry> = {}): WatchEntry {
  return {
    id: 7,
    media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
    tmdb_id: 100,
    watched_at: '2026-01-01T00:00:00Z',
    season_number: 1,
    episode_number: 2,
    created_at: '2026-01-01T00:00:00Z',
    title: 'Episode',
    poster_path: null,
    poster_url: null,
    vote_average: 0,
    show_name: 'Show',
    episode_type: '',
    ...overrides,
  }
}

describe('getRemoveHistoryConfirmText', () => {
  it('picks the episode or movie confirm key', () => {
    expect(
      getRemoveHistoryConfirmText(entry({ media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE })),
    ).toBe('This will remove the episode from your history, are you sure?')
    expect(
      getRemoveHistoryConfirmText(entry({ media_type: WATCH_ENTRY_MEDIA_TYPE.MOVIE })),
    ).toBe('This will remove the movie from your history, are you sure?')
  })
})

describe('useHistoryDelete', () => {
  it('deletes then runs the onDeleted refresh', async () => {
    trackingAPI.deleteHistory.mockClear()
    const deleted: WatchEntry[] = []
    const { deleteEntry, deletingEntryId } = useHistoryDelete({
      onDeleted: (e) => {
        deleted.push(e)
      },
    })

    await deleteEntry(entry())

    expect(trackingAPI.deleteHistory).toHaveBeenCalledWith(7)
    expect(deleted).toHaveLength(1)
    expect(deletingEntryId.value).toBeNull()
  })

  it('ignores concurrent deletes while one is in flight', async () => {
    trackingAPI.deleteHistory.mockClear()
    let release!: () => void
    trackingAPI.deleteHistory.mockImplementationOnce(
      () => new Promise<void>((resolve) => {
        release = () => resolve()
      }),
    )
    const { deleteEntry } = useHistoryDelete({ onDeleted: () => {} })

    const pending = deleteEntry(entry({ id: 1 }))
    await deleteEntry(entry({ id: 2 }))
    release()
    await pending

    expect(trackingAPI.deleteHistory).toHaveBeenCalledTimes(1)
    trackingAPI.deleteHistory.mockReset()
    trackingAPI.deleteHistory.mockResolvedValue(undefined)
  })

  it('resets state when the API fails', async () => {
    trackingAPI.deleteHistory.mockRejectedValueOnce(new Error('boom'))
    const { deleteEntry, deletingEntryId } = useHistoryDelete({ onDeleted: () => {} })

    await deleteEntry(entry())

    expect(deletingEntryId.value).toBeNull()
  })
})
