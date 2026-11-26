import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import CardStatusBadge from '@/components/cards/primitives/CardStatusBadge.vue'
import type { WatchEntryStatus } from '@/types/tracking'

describe('CardStatusBadge', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it.each([
    ['watched', 'bg-emerald-600'],
    ['watching', 'bg-brand-500'],
    ['plan_to_watch', 'bg-indigo-600'],
    ['dropped', 'bg-rose-600'],
  ] as const)('colours a %s title with %s', (status, colorClass) => {
    const wrapper = mount(CardStatusBadge, { props: { status } })

    expect(wrapper.classes()).toContain(colorClass)
  })

  it('treats the watched flag as watched when there is no status', () => {
    const wrapper = mount(CardStatusBadge, { props: { watched: true } })

    expect(wrapper.classes()).toContain('bg-emerald-600')
  })

  it('uses the neutral colour without a status', () => {
    const wrapper = mount(CardStatusBadge)

    expect(wrapper.classes()).toContain('bg-surface-300')
  })

  it('falls back to the neutral colour for a status it does not know', () => {
    const wrapper = mount(CardStatusBadge, { props: { status: 'on_hold' as WatchEntryStatus } })

    expect(wrapper.classes()).toContain('bg-surface-300')
  })
})
