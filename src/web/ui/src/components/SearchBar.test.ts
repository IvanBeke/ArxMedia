import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '@/components/SearchBar.vue'
import { required } from '@/test-support/assertions'

describe('SearchBar', () => {
  it('clears the query before navigating to a preview item', async () => {
    const wrapper = mount(SearchBar, {
      props: {
        modelValue: 'blade',
        enablePreview: true,
      },
    })

    await wrapper.vm.selectPreview({
      id: 42,
      media_type: 'movie',
      title: 'Blade Runner',
    })

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(required(wrapper.emitted('update:modelValue'), 'Model value events').at(-1)).toEqual([''])
    expect(wrapper.emitted('select-preview')).toBeTruthy()
    expect(required(required(wrapper.emitted('select-preview'), 'Preview events')[0], 'Preview event payload')[0]).toMatchObject({
      id: 42,
      media_type: 'movie',
      title: 'Blade Runner',
    })
  })

  it('submits an empty query when the clear button is clicked', async () => {
    const wrapper = mount(SearchBar, {
      props: {
        modelValue: 'blade',
        enablePreview: false,
        submitOnClear: true,
      },
    })

    await wrapper.find('button[aria-label="Clear search"]').trigger('click')

    expect(wrapper.emitted('submit')).toEqual([[{ query: '', scope: 'all' }]])
  })
})
