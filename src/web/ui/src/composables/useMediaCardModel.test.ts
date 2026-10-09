import { describe, expect, it } from 'vitest'
import { WATCH_ENTRY_MEDIA_TYPE } from '@/constants/tracking'
import { useMediaCardModel } from '@/composables/useMediaCardModel'

function episodeEntry(season_number: number | null, episode_number: number | null) {
  return {
    media_type: WATCH_ENTRY_MEDIA_TYPE.EPISODE,
    tmdb_id: 60728,
    season_number,
    episode_number,
    title: 'Special One',
  }
}

describe('useMediaCardModel episodeCode', () => {
  it('shows the code pill for specials (season 0)', () => {
    const { model } = useMediaCardModel('mixed', episodeEntry(0, 1), {})

    expect(model.value.episodeCode.visible).toBe(true)
    expect(model.value.episodeCode.seasonNumber).toBe(0)
    expect(model.value.episodeCode.episodeNumber).toBe(1)
  })

  it('shows the code pill for regular episodes', () => {
    const { model } = useMediaCardModel('mixed', episodeEntry(1, 2), {})

    expect(model.value.episodeCode.visible).toBe(true)
  })

  it('hides the code pill when season or episode is unknown', () => {
    expect(useMediaCardModel('mixed', episodeEntry(null, 1), {}).model.value.episodeCode.visible).toBe(false)
    expect(useMediaCardModel('mixed', episodeEntry(1, null), {}).model.value.episodeCode.visible).toBe(false)
  })
})
