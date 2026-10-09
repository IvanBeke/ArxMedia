import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LoadError from '@/components/LoadError.vue'
import { usePreferencesStore } from '@/stores/preferences'

describe('LoadError', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('offers a retry in English by default', () => {
    const wrapper = mount(LoadError, { props: { message: 'Could not load Up Next.' } })

    expect(wrapper.get('button').text()).toBe('Try again')
  })

  it('offers a retry in Spanish when the locale is Spanish', () => {
    usePreferencesStore().setLocale('es')
    const wrapper = mount(LoadError, { props: { message: 'Could not load Up Next.' } })

    expect(wrapper.get('button').text()).toBe('Reintentar')
  })
})
