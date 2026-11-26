import { describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { retryFailed, useStatsSection } from '@/composables/useStatsSection'

function deferred<T>() {
  let resolve: (value: T) => void = () => {}
  let reject: (reason: unknown) => void = () => {}
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

function section<T>(fetcher: (username: string) => Promise<T>, options?: Parameters<typeof useStatsSection<T>>[2], username = ref('bob')) {
  const scope = effectScope()
  const stats = scope.run(() => useStatsSection(() => username.value, fetcher, options))!
  return { stats, username, scope }
}

describe('useStatsSection', () => {
  it('loads for the username and exposes the data', async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 1 })
    const { stats } = section(fetcher)

    expect(stats.loading).toBe(true)
    await flushPromises()

    expect(fetcher).toHaveBeenCalledWith('bob')
    expect(stats.data).toEqual({ value: 1 })
    expect(stats.loading).toBe(false)
    expect(stats.error).toBe(false)
  })

  it('flags a 403 as forbidden and any other failure as an error', async () => {
    const forbidden = section(vi.fn().mockRejectedValue({ status: 403 })).stats
    const failing = section(vi.fn().mockRejectedValue({ status: 500 })).stats
    await flushPromises()

    expect([forbidden.forbidden, forbidden.error, forbidden.loading]).toEqual([true, false, false])
    expect([failing.forbidden, failing.error, failing.loading]).toEqual([false, true, false])
  })

  it('reloads when the username changes and drops the previous data meanwhile', async () => {
    const next = deferred<{ username: string }>()
    const fetcher = vi.fn().mockResolvedValueOnce({ username: 'bob' }).mockReturnValueOnce(next.promise)
    const { stats, username } = section(fetcher)
    await flushPromises()
    expect(stats.data).toEqual({ username: 'bob' })

    username.value = 'carol'
    await nextTick()
    expect(fetcher).toHaveBeenLastCalledWith('carol')
    expect(stats.data).toBeNull()
    expect(stats.loading).toBe(true)

    next.resolve({ username: 'carol' })
    await flushPromises()

    expect(stats.data).toEqual({ username: 'carol' })
  })

  it('keeps the current data on screen while load() fetches again', async () => {
    const refreshed = deferred<string>()
    const fetcher = vi.fn().mockResolvedValueOnce('first').mockReturnValueOnce(refreshed.promise)
    const { stats } = section(fetcher)
    await flushPromises()

    void stats.load()
    await nextTick()

    expect(stats.data).toBe('first')
    expect(stats.loading).toBe(true)

    refreshed.resolve('second')
    await flushPromises()

    expect(stats.data).toBe('second')
    expect(stats.loading).toBe(false)
  })

  it('keeps the data when a refresh fails, and flags the error', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce('first').mockRejectedValueOnce({ status: 500 })
    const { stats } = section(fetcher)
    await flushPromises()

    await stats.load()

    expect(stats.data).toBe('first')
    expect(stats.error).toBe(true)
  })

  it('keeps the data on screen when the refreshOn value changes', async () => {
    const year = ref(2025)
    const next = deferred<string>()
    const fetcher = vi.fn().mockResolvedValueOnce('2025 data').mockReturnValueOnce(next.promise)
    const { stats } = section(fetcher, { refreshOn: () => year.value })
    await flushPromises()
    expect(stats.data).toBe('2025 data')

    year.value = 2024
    await nextTick()

    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(stats.data).toBe('2025 data')
    expect(stats.loading).toBe(true)

    next.resolve('2024 data')
    await flushPromises()
    expect(stats.data).toBe('2024 data')
  })

  it('ignores a response that a newer request made stale', async () => {
    const first = deferred<string>()
    const second = deferred<string>()
    const fetcher = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const { stats, username } = section(fetcher)

    username.value = 'carol'
    await nextTick()
    second.resolve('carol data')
    await flushPromises()
    first.resolve('bob data')
    await flushPromises()

    expect(stats.data).toBe('carol data')
    expect(stats.loading).toBe(false)
  })

  it('does not fetch while disabled or without a username, and fetches once enabled', async () => {
    const fetcher = vi.fn().mockResolvedValue('data')
    const enabled = ref(false)
    const { stats } = section(fetcher, { enabled: () => enabled.value })
    const unnamed = section(fetcher, undefined, ref('')).stats
    await flushPromises()

    expect(fetcher).not.toHaveBeenCalled()
    expect([stats.loading, unnamed.loading]).toEqual([false, false])

    enabled.value = true
    await flushPromises()

    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(stats.data).toBe('data')
  })

  it('retryFailed reloads only the sections in error', async () => {
    const ok = vi.fn().mockResolvedValue('ok')
    const failing = vi.fn().mockRejectedValueOnce({ status: 500 }).mockResolvedValue('fixed')
    const healthy = section(ok).stats
    const broken = section(failing).stats
    await flushPromises()

    retryFailed(healthy, broken)
    await flushPromises()

    expect(ok).toHaveBeenCalledTimes(1)
    expect(failing).toHaveBeenCalledTimes(2)
    expect(broken.data).toBe('fixed')
  })
})
