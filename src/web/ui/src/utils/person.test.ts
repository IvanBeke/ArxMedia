import { describe, expect, it } from 'vitest'
import { ageFor, creditRole, creditYear, dedupeCredits, filterByMedia, genderLabel, groupCreditsByYear, isSelfCredit, knownCreditsCount, topKnownFor, truncateAtWord } from '@/utils/person'
import type { PersonCredit } from '@/types/api'

function credit(partial: Partial<PersonCredit> & { id: number }): PersonCredit {
  return { media_type: 'movie', ...partial } as PersonCredit
}

describe('person utils', () => {
  it('maps gender codes', () => {
    expect(genderLabel(1)).toBe('Female')
    expect(genderLabel(2)).toBe('Male')
    expect(genderLabel(0)).toBe('—')
    expect(genderLabel(null)).toBe('—')
    expect(genderLabel(undefined)).toBe('—')
  })

  it('computes age in full years', () => {
    expect(ageFor('1965-09-17', '2026-09-16')).toBe(60)
    expect(ageFor('1965-09-17', '2026-09-17')).toBe(61)
    expect(ageFor('invalid')).toBeNull()
    expect(ageFor(null)).toBeNull()
  })

  it('prefers the first credit air date when resolving a credit year', () => {
    expect(creditYear(credit({ id: 1, release_date: '2019-05-31' }))).toBe(2019)
    expect(creditYear(credit({
      id: 2,
      media_type: 'tv',
      first_air_date: '2015-03-04',
      first_credit_air_date: '2024-06-12',
    }))).toBe(2024)
    expect(creditYear(credit({ id: 3, media_type: 'tv', first_air_date: '2015-03-04' }))).toBe(2015)
    expect(creditYear(credit({ id: 4 }))).toBeNull()
  })

  it('groups credits by effective year and orders each group newest first', () => {
    const groups = groupCreditsByYear([
      credit({ id: 1, title: 'A Movie', release_date: '2019-01-01' }),
      credit({ id: 2, title: 'Z Movie', release_date: '2019-06-01' }),
      credit({
        id: 3,
        name: 'Game of Thrones',
        media_type: 'tv',
        first_air_date: '2011-04-17',
        first_credit_air_date: '2014-05-11',
      }),
      credit({
        id: 4,
        name: 'Inside No. 9',
        media_type: 'tv',
        first_air_date: '2014-02-05',
        first_credit_air_date: '2024-06-12',
      }),
      credit({
        id: 5,
        name: 'Moonflower Murders',
        media_type: 'tv',
        first_air_date: '2024-11-16',
        first_credit_air_date: '2024-11-16',
      }),
      credit({ id: 6, title: 'Mystery' }),
    ])
    expect(groups.map((group) => group.label)).toEqual(['2024', '2019', '2014', '—'])
    expect(groups[0]?.items.map((item) => item.name)).toEqual(['Moonflower Murders', 'Inside No. 9'])
    expect(groups[1]?.items.map((item) => item.title)).toEqual(['Z Movie', 'A Movie'])
  })

  it('filters by media type and ranks known-for by popularity', () => {
    const items = [
      credit({ id: 1, media_type: 'movie', popularity: 5 }),
      credit({ id: 2, media_type: 'tv', popularity: 50 }),
      credit({ id: 3, media_type: 'movie', popularity: 20 }),
    ]
    expect(filterByMedia(items, 'movie').map((item) => item.id)).toEqual([1, 3])
    expect(topKnownFor(items, 2).map((item) => item.id)).toEqual([2, 3])
  })

  it('counts known credits across cast and crew', () => {
    expect(knownCreditsCount(null)).toBe(0)
    expect(knownCreditsCount({
      cast: [credit({ id: 1 }), credit({ id: 2 })],
      crew: [credit({ id: 3 })],
    })).toBe(3)
  })

  it('truncates biography previews at word boundaries', () => {
    expect(truncateAtWord('Short bio', 600)).toBe('Short bio')
    expect(truncateAtWord('  Padded bio  ', 600)).toBe('Padded bio')
    const source = 'word '.repeat(200).trimEnd()
    const preview = truncateAtWord(source, 600)
    expect(preview.endsWith('…')).toBe(true)
    const body = preview.slice(0, -1)
    expect(source.startsWith(body)).toBe(true)
    expect(source[body.length]).toBe(' ')
    expect(truncateAtWord('Supercalifragilisticexpialidocious', 10)).toBe('Supercalif…')
  })

  it('dedupes credits by media and id keeping the most popular', () => {
    const items = [
      credit({ id: 1, media_type: 'tv', character: 'Old', popularity: 3 }),
      credit({ id: 1, media_type: 'tv', character: 'New', popularity: 30 }),
      credit({ id: 1, media_type: 'movie', character: 'Film', popularity: 1 }),
    ]
    const deduped = dedupeCredits(items)
    expect(deduped).toHaveLength(2)
    expect(deduped.find((item) => item.media_type === 'tv')?.character).toBe('New')
  })

  it('detects self cameos and deprioritizes them in known-for', () => {
    expect(isSelfCredit(credit({ id: 1, character: 'Self' }))).toBe(true)
    expect(isSelfCredit(credit({ id: 2, character: 'Self - Guest' }))).toBe(true)
    expect(isSelfCredit(credit({ id: 3, character: 'Eric Taylor' }))).toBe(false)
    expect(isSelfCredit(credit({ id: 4 }))).toBe(false)
    const ranked = topKnownFor([
      credit({ id: 1, character: 'Self', popularity: 99 }),
      credit({ id: 2, character: 'Lead Role', popularity: 5 }),
    ], 2)
    expect(ranked.map((item) => item.id)).toEqual([2, 1])
  })

  it('resolves credit roles from character or job', () => {
    expect(creditRole(credit({ id: 1, character: 'Peter Parker' }))).toBe('Peter Parker')
    expect(creditRole(credit({ id: 2, job: 'Director' }))).toBe('Director')
    expect(creditRole(credit({ id: 3, character: '  Hal Jordan  ' }))).toBe('Hal Jordan')
    expect(creditRole(credit({ id: 4 }))).toBe('')
  })
})
