import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useFlashMessages } from '@/composables/useFlashMessages'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useFlashMessages', () => {
  it('shows a success message and clears it after the success duration', () => {
    const { successMsg, errorMsg, showSuccess } = useFlashMessages()

    showSuccess('Done!')
    expect(successMsg.value).toBe('Done!')
    expect(errorMsg.value).toBe('')

    vi.advanceTimersByTime(2500)
    expect(successMsg.value).toBe('')
  })

  it('shows an error message and clears it after the error duration', () => {
    const { successMsg, errorMsg, showError } = useFlashMessages()

    showError('Bad!')
    expect(errorMsg.value).toBe('Bad!')
    expect(successMsg.value).toBe('')

    vi.advanceTimersByTime(3500)
    expect(errorMsg.value).toBe('')
  })

  it('showing one kind dismisses the other immediately', () => {
    const { successMsg, errorMsg, showSuccess, showError } = useFlashMessages()

    showError('Bad!')
    showSuccess('Done!')
    expect(errorMsg.value).toBe('')
    expect(successMsg.value).toBe('Done!')

    showError('Bad again!')
    expect(successMsg.value).toBe('')
    expect(errorMsg.value).toBe('Bad again!')
  })

  it('a stale timer does not clear a newer message', () => {
    const { successMsg, showSuccess } = useFlashMessages()

    showSuccess('First')
    vi.advanceTimersByTime(2000)
    showSuccess('Second')
    vi.advanceTimersByTime(2000)

    expect(successMsg.value).toBe('Second')
    vi.advanceTimersByTime(500)
    expect(successMsg.value).toBe('')
  })

  it('honors custom durations when provided', () => {
    const { successMsg, errorMsg, showSuccess, showError } = useFlashMessages({
      successDurationMs: 1800,
      errorDurationMs: 3000,
    })

    showSuccess('Quick')
    vi.advanceTimersByTime(1799)
    expect(successMsg.value).toBe('Quick')
    vi.advanceTimersByTime(100)
    expect(successMsg.value).toBe('')

    showError('Slow')
    vi.advanceTimersByTime(2999)
    expect(errorMsg.value).toBe('Slow')
    vi.advanceTimersByTime(100)
    expect(errorMsg.value).toBe('')
  })
})
