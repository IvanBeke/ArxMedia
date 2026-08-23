import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'

beforeEach(() => {
  setActivePinia(createPinia())
  if (!globalThis.Temporal) {
    globalThis.Temporal = TemporalPolyfill
  }
  if (!Date.prototype.toTemporalInstant) {
    Date.prototype.toTemporalInstant = toTemporalInstant
  }
})

describe('tmdbImageUrl', () => {
  it('builds image urls with the given or default size', async () => {
    const { tmdbImageUrl } = await import('@/utils/images')
    expect(tmdbImageUrl('/abc.jpg')).toBe('https://image.tmdb.org/t/p/w500/abc.jpg')
    expect(tmdbImageUrl('/abc.jpg', 'w92')).toBe('https://image.tmdb.org/t/p/w92/abc.jpg')
    expect(tmdbImageUrl('')).toBeNull()
    expect(tmdbImageUrl(null)).toBeNull()
  })
})

describe('mediaStatus', () => {
  it('allows rating for watched, watching and dropped statuses only', async () => {
    const { canRateByStatus } = await import('@/utils/mediaStatus')
    const { WATCH_ENTRY_STATUS } = await import('@/constants/tracking')

    expect(canRateByStatus(WATCH_ENTRY_STATUS.WATCHED)).toBe(true)
    expect(canRateByStatus(WATCH_ENTRY_STATUS.WATCHING)).toBe(true)
    expect(canRateByStatus(WATCH_ENTRY_STATUS.DROPPED)).toBe(true)
    expect(canRateByStatus(WATCH_ENTRY_STATUS.PLAN_TO_WATCH)).toBe(false)
    expect(canRateByStatus(WATCH_ENTRY_STATUS.NONE)).toBe(false)
    expect(canRateByStatus(undefined)).toBe(false)
  })

  it('labels missing metadata timestamps as unknown', async () => {
    const { formatUpdatedAtLabel } = await import('@/utils/mediaStatus')
    expect(formatUpdatedAtLabel(null)).toBe('Unknown')
    expect(formatUpdatedAtLabel('not-a-date')).toBe('Unknown')
    expect(formatUpdatedAtLabel('2026-08-19T09:07:00Z')).toContain('2026')
  })
})

describe('watchedTooltipText', () => {
  it('describes unwatched, watched and watched-on states', async () => {
    const { watchedTooltipText } = await import('@/utils/watchOptions')
    const { useI18n } = await import('@/i18n')
    const { t } = useI18n()

    expect(watchedTooltipText(false, '', t)).toBe(t('tracking_mark_as_watched'))
    expect(watchedTooltipText(true, '', t)).toBe(t('tracking_watched'))

    const withDate = watchedTooltipText(true, '2026-08-19T09:07:00Z', t)
    expect(withDate).toContain(t('tracking_watched_on'))
    expect(withDate).toContain('2026')
  })
})
