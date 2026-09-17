import { describe, expect, it } from 'vitest'
import router from '@/router'

// Project rule: every page requires authentication except the public
// landing, login, registration and offline-connectivity pages.
// (/offline renders no user data, so logged-out users can reach it.)
describe('route auth coverage', () => {
  it('requires auth on every route except /, /login, /register and /offline', () => {
    const publicPaths = new Set(['/', '/login', '/register', '/offline'])
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
