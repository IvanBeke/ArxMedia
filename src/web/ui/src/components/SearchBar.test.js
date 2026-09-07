import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchBar from '@/components/SearchBar.vue'

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
      kind: 'movie',
      title: 'Blade Runner',
    })

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([''])
    expect(wrapper.emitted('select-preview')).toBeTruthy()
    expect(wrapper.emitted('select-preview')[0][0]).toMatchObject({
      id: 42,
      media_type: 'movie',
      title: 'Blade Runner',
    })
  })
})
