import { describe, expect, it } from 'vitest'
import { SERVICE_WORKER_URL, createWorkbox } from '@/pwa/client'

describe('pwa client', () => {
  it('serves the worker at root scope', () => {
    expect(SERVICE_WORKER_URL).toBe('/sw.js')
  })

  it('does not register outside production builds', () => {
    expect(import.meta.env.PROD).toBe(false)
    expect(createWorkbox()).toBeNull()
  })
})
