import { describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'

function mountWithLatestRequest() {
  let api: ReturnType<typeof useLatestRequest> | undefined
  const wrapper = mount(defineComponent({
    setup() {
      api = useLatestRequest()
      return () => null
    },
  }))
  if (!api) throw new Error('composable not initialised')
  return { wrapper, api }
}

describe('useLatestRequest', () => {
  it('cancels the previous request when a new one starts', () => {
    const { api } = mountWithLatestRequest()

    const first = api.next()
    const second = api.next()

    expect(first.aborted).toBe(true)
    expect(second.aborted).toBe(false)
  })

  it('cancels the in-flight request on unmount', () => {
    const { wrapper, api } = mountWithLatestRequest()
    const signal = api.next()

    wrapper.unmount()

    expect(signal.aborted).toBe(true)
  })

  it('recognises abort errors only', () => {
    expect(isAbortError(new DOMException('Aborted', 'AbortError'))).toBe(true)
    expect(isAbortError(new Error('boom'))).toBe(false)
    expect(isAbortError({ detail: 'nope' })).toBe(false)
  })
})
