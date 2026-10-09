import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MEDIA_TYPE } from '@/constants/tracking'
import { createTransientIdState } from '@/composables/useTransientIdState'

describe('createTransientIdState', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('tracks loading per media type and guards concurrent runs', async () => {
    const state = createTransientIdState()
    let release!: () => void
    const gate = new Promise<void>((resolve) => { release = resolve })

    const first = state.runWithLoading(MEDIA_TYPE.MOVIE, 7, () => gate)
    expect(state.isLoading(MEDIA_TYPE.MOVIE, 7)).toBe(true)
    expect(state.isLoading(MEDIA_TYPE.TV, 7)).toBe(false)

    await expect(state.runWithLoading(MEDIA_TYPE.MOVIE, 7, async () => 'late')).resolves.toBeNull()
    release()
    await expect(first).resolves.toBeUndefined()
    expect(state.isLoading(MEDIA_TYPE.MOVIE, 7)).toBe(false)
  })

  it('pulses and clears the pulse after the timeout', () => {
    const state = createTransientIdState(500)

    state.triggerPulse(MEDIA_TYPE.TV, 9)
    expect(state.isPulsing(MEDIA_TYPE.TV, 9)).toBe(true)

    vi.advanceTimersByTime(499)
    expect(state.isPulsing(MEDIA_TYPE.TV, 9)).toBe(true)
    vi.advanceTimersByTime(1)
    expect(state.isPulsing(MEDIA_TYPE.TV, 9)).toBe(false)
  })

  it('restarts the pulse timer when retriggered', () => {
    const state = createTransientIdState(500)
    state.triggerPulse(MEDIA_TYPE.MOVIE, 3)
    vi.advanceTimersByTime(400)
    state.triggerPulse(MEDIA_TYPE.MOVIE, 3)

    vi.advanceTimersByTime(400)
    expect(state.isPulsing(MEDIA_TYPE.MOVIE, 3)).toBe(true)
    vi.advanceTimersByTime(100)
    expect(state.isPulsing(MEDIA_TYPE.MOVIE, 3)).toBe(false)
  })

  it('reset clears state and pending pulse timers', () => {
    const state = createTransientIdState()
    state.triggerPulse(MEDIA_TYPE.MOVIE, 3)
    state.resetTransientState()

    expect(state.isPulsing(MEDIA_TYPE.MOVIE, 3)).toBe(false)
    vi.advanceTimersByTime(1000)
    expect(state.isPulsing(MEDIA_TYPE.MOVIE, 3)).toBe(false)
  })
})
