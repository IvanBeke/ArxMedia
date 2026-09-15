import { describe, expect, it } from 'vitest'
import type { RouteLocationNormalized, RouteLocationNormalizedLoaded } from 'vue-router'
import { resolveScrollPosition } from '@/router'

function route(path: string, query: Record<string, string> = {}) {
  return { path, query } as unknown as RouteLocationNormalized & RouteLocationNormalizedLoaded
}

describe('resolveScrollPosition', () => {
  it('scrolls to top on path changes', () => {
    expect(resolveScrollPosition(route('/tv/1'), route('/tv/2'), null)).toEqual({ top: 0 })
  })

  it('preserves scroll when only the tab query changes', () => {
    expect(resolveScrollPosition(route('/tv/1', { tab: 'cast' }), route('/tv/1', { tab: 'overview' }), null)).toBeUndefined()
  })

  it('preserves scroll when the tab query is added or removed', () => {
    expect(resolveScrollPosition(route('/tv/1', { tab: 'cast' }), route('/tv/1'), null)).toBeUndefined()
    expect(resolveScrollPosition(route('/tv/1'), route('/tv/1', { tab: 'cast' }), null)).toBeUndefined()
  })

  it('scrolls to top when other query params change', () => {
    expect(resolveScrollPosition(route('/search', { q: 'dune', page: '2' }), route('/search', { q: 'dune', page: '1' }), null)).toEqual({ top: 0 })
  })

  it('restores the saved position on back/forward', () => {
    const saved = { left: 0, top: 420 }
    expect(resolveScrollPosition(route('/tv/1'), route('/tv/1'), saved)).toEqual(saved)
  })
})
