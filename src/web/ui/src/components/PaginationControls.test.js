import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PaginationControls from '@/components/PaginationControls.vue'

function pageNumberButtons(wrapper) {
  return wrapper
    .findAll('button')
    .map((button) => button.text())
    .filter((text) => /^\d+$/.test(text))
}

function lastTotalPages(wrapper) {
  const events = wrapper.emitted('update:totalPages')
  return events[events.length - 1][0]
}

describe('PaginationControls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('computes total pages from count and the calibrated first-page size', () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 1, loadedCount: 20 },
    })

    expect(lastTotalPages(wrapper)).toBe(3)
    expect(pageNumberButtons(wrapper)).toEqual(['1', '2', '3'])
  })

  it('does not shrink the page size when loading a partial last page', async () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 1, loadedCount: 20 },
    })

    await wrapper.setProps({ page: 3, loadedCount: 7 })

    expect(lastTotalPages(wrapper)).toBe(3)
    expect(pageNumberButtons(wrapper)).toEqual(['1', '2', '3'])
  })

  it('keeps the bootstrap page size until a full first page calibrates it', async () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 3, loadedCount: 0 },
    })

    expect(lastTotalPages(wrapper)).toBe(3)

    await wrapper.setProps({ page: 1, loadedCount: 25 })

    expect(lastTotalPages(wrapper)).toBe(2)
    expect(pageNumberButtons(wrapper)).toEqual(['1', '2'])
  })

  it('grows the page count again when the count increases', async () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 1, loadedCount: 20 },
    })

    await wrapper.setProps({ count: 61 })

    expect(lastTotalPages(wrapper)).toBe(4)
  })

  it('hides itself when everything fits on one page', () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 10, page: 1, loadedCount: 10 },
    })

    expect(lastTotalPages(wrapper)).toBe(1)
    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('emits go with the clicked page number', async () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 1, loadedCount: 20 },
    })

    const pageTwoButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '2')
    await pageTwoButton.trigger('click')

    expect(wrapper.emitted('go')).toEqual([[2]])
  })

  it('clamps an out-of-range current page for display', () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 99, loadedCount: 0 },
    })

    expect(lastTotalPages(wrapper)).toBe(3)
    expect(wrapper.emitted('go')).toBeUndefined()
  })

  it('suppresses go events for the current page and out-of-range requests', async () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 2, loadedCount: 20 },
    })

    const activePageButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '2' && button.classes().includes('pagination-btn-active'))
    await activePageButton.trigger('click')

    const nextButton = wrapper.findAll('button').find((button) => button.attributes('aria-label') === 'Go to page 3')
    await nextButton.trigger('click')
    expect(wrapper.emitted('go')).toEqual([[3]])

    await wrapper.setProps({ page: 3 })
    await nextButton.trigger('click')
    expect(wrapper.emitted('go')).toHaveLength(1)
  })

  it('suppresses go events while disabled', async () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 1, loadedCount: 20, disabled: true },
    })

    const pageTwoButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '2')
    await pageTwoButton.trigger('click')

    expect(wrapper.emitted('go')).toBeUndefined()
  })

  it('emits update:page when committed data shrinks below the current page', async () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 3, loadedCount: 0 },
    })
    expect(wrapper.emitted('update:page')).toBeUndefined()

    // Data shrinks from 47 to 40 items: pages drop from 3 to 2 while the user sits on 3.
    await wrapper.setProps({ count: 40 })

    expect(wrapper.emitted('update:page')).toEqual([[2]])
  })

  it('emits a corrective page on mount when the requested page is out of range', () => {
    const wrapper = mount(PaginationControls, {
      props: { count: 47, page: 99, loadedCount: 0 },
    })

    expect(wrapper.emitted('update:page')).toEqual([[3]])
  })
})
