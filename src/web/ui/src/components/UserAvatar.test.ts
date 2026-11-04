import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import UserAvatar from '@/components/UserAvatar.vue'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('UserAvatar', () => {
  it('shows the picture when there is one', () => {
    const wrapper = mount(UserAvatar, { props: { username: 'alex', src: '/media/avatars/a/avatar.webp' } })

    const img = wrapper.get('img')
    expect(img.attributes('src')).toBe('/media/avatars/a/avatar.webp')
    expect(img.attributes('alt')).toBe('alex avatar')
    expect(img.classes()).toContain('rounded-full')
  })

  it('falls back to the capitalised initial', () => {
    const wrapper = mount(UserAvatar, { props: { username: 'alex', src: null } })

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toBe('A')
  })

  it('applies the size classes', () => {
    const wrapper = mount(UserAvatar, { props: { username: 'alex', size: 'lg' } })

    expect(wrapper.classes()).toEqual(expect.arrayContaining(['h-16', 'w-16', 'rounded-full']))
  })
})
