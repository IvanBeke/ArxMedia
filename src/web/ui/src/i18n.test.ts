import { describe, expect, it } from 'vitest'
import { messages } from '@/i18n'

// Same text in both languages (loanwords, abbreviations, templates), so identical values are expected.
const SAME_IN_BOTH_LANGUAGES = new Set([
  'avatar_zoom',
  'sonarr_series_type_anime',
  'filter_bar_direction_asc',
  'filter_bar_direction_desc',
  'user_rating_title',
  'common_no',
  'show_minutes_per_episode',
  'episode_runtime_minutes',
])

const placeholders = (value: string) => [...value.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()

describe('i18n messages', () => {
  it('defines the same keys in English and Spanish', () => {
    const en = Object.keys(messages.en).sort()
    const es = Object.keys(messages.es).sort()

    expect(es.filter((key) => !en.includes(key))).toEqual([])
    expect(en.filter((key) => !es.includes(key))).toEqual([])
  })

  it('keeps the same placeholders in every translation', () => {
    const mismatched = Object.keys(messages.en).filter((key) => {
      const en = messages.en[key as keyof typeof messages.en]
      const es = messages.es[key as keyof typeof messages.es]
      return JSON.stringify(placeholders(en)) !== JSON.stringify(placeholders(es))
    })

    expect(mismatched).toEqual([])
  })

  it('translates every Spanish message', () => {
    const untranslated = Object.keys(messages.en).filter((key) => {
      const en = messages.en[key as keyof typeof messages.en]
      const es = messages.es[key as keyof typeof messages.es]
      return en === es && !SAME_IN_BOTH_LANGUAGES.has(key)
    })

    expect(untranslated).toEqual([])
  })
})
