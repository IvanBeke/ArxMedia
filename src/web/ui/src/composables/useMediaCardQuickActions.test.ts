import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { MEDIA_TYPE } from '@/constants/tracking'
import { useMediaCardQuickActions } from '@/composables/useMediaCardQuickActions'
import { usePreferencesStore } from '@/stores/preferences'

describe('getWatchlistAriaLabel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the base label when not in the watchlist', () => {
    const { getWatchlistAriaLabel } = useMediaCardQuickActions()

    expect(getWatchlistAriaLabel(MEDIA_TYPE.MOVIE, false)).toBe('Add movie to watchlist')
  })

  it('appends the added date when the item is in the watchlist', () => {
    const { getWatchlistAriaLabel } = useMediaCardQuickActions()

    const label = getWatchlistAriaLabel(MEDIA_TYPE.TV, true, '2024-01-05T10:00:00Z')

    expect(label).toContain('Remove show from watchlist')
    expect(label).toContain('2024')
  })

  it('omits the date when none is stored', () => {
    const { getWatchlistAriaLabel } = useMediaCardQuickActions()

    expect(getWatchlistAriaLabel(MEDIA_TYPE.MOVIE, true, null)).toBe('Remove movie from watchlist')
  })

  it('formats the date in the active locale', () => {
    usePreferencesStore().setLocale('es')
    const { getWatchlistAriaLabel } = useMediaCardQuickActions()

    expect(getWatchlistAriaLabel(MEDIA_TYPE.MOVIE, true, '2024-01-05T10:00:00Z')).toContain('Añadido el')
  })
})
