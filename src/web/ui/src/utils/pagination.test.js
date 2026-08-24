import { describe, expect, it } from 'vitest'
import {
  DEFAULT_PAGE_SIZE,
  invalidPageRecovery,
  normalizePagedResponse,
  parsePage,
} from '@/utils/pagination'

describe('parsePage', () => {
  it('parses valid positive integers', () => {
    expect(parsePage('3')).toBe(3)
    expect(parsePage(7)).toBe(7)
    expect(parsePage('012')).toBe(12)
  })

  it('falls back on invalid input', () => {
    expect(parsePage(undefined)).toBe(1)
    expect(parsePage(null)).toBe(1)
    expect(parsePage('')).toBe(1)
    expect(parsePage('abc')).toBe(1)
    expect(parsePage('0')).toBe(1)
    expect(parsePage('-4')).toBe(1)
    expect(parsePage('2.9')).toBe(2)
    expect(parsePage('abc', 5)).toBe(5)
  })
})

describe('normalizePagedResponse', () => {
  it('normalizes a DRF envelope', () => {
    const paged = normalizePagedResponse({ count: 47, results: [{ id: 1 }, { id: 2 }] })
    expect(paged).toEqual({ items: [{ id: 1 }, { id: 2 }], count: 47, loadedCount: 2 })
  })

  it('derives count from results when missing', () => {
    const paged = normalizePagedResponse({ results: [1, 2, 3] })
    expect(paged).toEqual({ items: [1, 2, 3], count: 3, loadedCount: 3 })
  })

  it('normalizes bare array payloads as single-page data', () => {
    const paged = normalizePagedResponse(['a', 'b'])
    expect(paged).toEqual({ items: ['a', 'b'], count: 2, loadedCount: 0 })
  })

  it('tolerates empty and null payloads', () => {
    expect(normalizePagedResponse(undefined)).toEqual({ items: [], count: 0, loadedCount: 0 })
    expect(normalizePagedResponse({})).toEqual({ items: [], count: 0, loadedCount: 0 })
  })
})

describe('invalidPageRecovery', () => {
  const invalidPage404 = { status: 404, detail: 'Invalid page.' }

  it('recovers to the fallback page for out-of-range requests', () => {
    expect(invalidPageRecovery(invalidPage404, 99)).toBe(1)
    expect(invalidPageRecovery(invalidPage404, 5)).toBe(1)
  })

  it('ignores invalid-page errors when already on or below the fallback', () => {
    expect(invalidPageRecovery(invalidPage404, 1)).toBeNull()
    expect(invalidPageRecovery(invalidPage404, 0)).toBeNull()
  })

  it('ignores unrelated errors and lookalikes', () => {
    expect(invalidPageRecovery({ status: 500, detail: 'Invalid page.' }, 9)).toBeNull()
    expect(invalidPageRecovery({ status: 404, detail: 'Not found.' }, 9)).toBeNull()
    expect(invalidPageRecovery(new Error('boom'), 9)).toBeNull()
    expect(invalidPageRecovery(null, 9)).toBeNull()
  })
})

describe('DEFAULT_PAGE_SIZE', () => {
  it('mirrors the server page size', () => {
    expect(DEFAULT_PAGE_SIZE).toBe(20)
  })
})
