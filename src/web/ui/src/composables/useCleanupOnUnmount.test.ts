import { describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { useCleanupOnUnmount } from '@/composables/useCleanupOnUnmount'

describe('useCleanupOnUnmount', () => {
  it('runs cleanup when the component unmounts', () => {
    const cleanup = vi.fn()
    const wrapper = mount(defineComponent({
      setup() {
        useCleanupOnUnmount(cleanup)
        return () => null
      },
    }))

    expect(cleanup).not.toHaveBeenCalled()
    wrapper.unmount()
    expect(cleanup).toHaveBeenCalledTimes(1)
  })

  it('is a silent no-op outside setup', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(() => useCleanupOnUnmount(() => {})).not.toThrow()
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })
})
