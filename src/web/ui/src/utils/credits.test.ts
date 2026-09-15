import { describe, expect, it } from 'vitest'
import { creditLine } from '@/utils/credits'
import type { Person } from '@/types/api'

function person(overrides: Partial<Person>): Person {
  return { id: 1, name: 'Test Person', ...overrides }
}

describe('creditLine', () => {
  it('returns the flat character for movie/episode cast', () => {
    expect(creditLine(person({ character: 'Joel Miller' }))).toBe('Joel Miller')
  })

  it('returns the flat job for crew', () => {
    expect(creditLine(person({ job: 'Director' }))).toBe('Director')
  })

  it('prefers character over job when both are present', () => {
    expect(creditLine(person({ character: 'Joel Miller', job: 'Producer' }))).toBe('Joel Miller')
  })

  it('joins aggregate roles', () => {
    expect(creditLine(person({
      roles: [{ character: 'Joel Miller' }, { character: 'Trooper #3' }],
    }))).toBe('Joel Miller, Trooper #3')
  })

  it('joins aggregate jobs', () => {
    expect(creditLine(person({
      jobs: [{ job: 'Director' }, { job: 'Writer' }],
    }))).toBe('Director, Writer')
  })

  it('prefers aggregate roles over flat fields', () => {
    expect(creditLine(person({
      character: 'Old Name',
      roles: [{ character: 'Joel Miller' }],
    }))).toBe('Joel Miller')
  })

  it('skips blank entries and returns empty string when nothing is set', () => {
    expect(creditLine(person({
      roles: [{ character: '  ' }, {}],
      jobs: [{ job: '' }],
    }))).toBe('')
    expect(creditLine(person({}))).toBe('')
  })
})
