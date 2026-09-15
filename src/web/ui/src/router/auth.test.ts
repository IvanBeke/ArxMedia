import { describe, expect, it } from 'vitest'
import router from '@/router'

// Project rule: every page requires authentication except the public
// landing, login and registration pages.
describe('route auth coverage', () => {
  it('requires auth on every route except /, /login and /register', () => {
    const publicPaths = new Set(['/', '/login', '/register'])
    const checked: string[] = []

    for (const record of router.getRoutes()) {
      checked.push(record.path)
      if (publicPaths.has(record.path)) {
        expect(record.meta.requiresAuth ?? false).toBe(false)
      } else {
        expect(record.meta.requiresAuth).toBe(true)
      }
    }

    expect(checked.length).toBeGreaterThan(0)
  })
})
