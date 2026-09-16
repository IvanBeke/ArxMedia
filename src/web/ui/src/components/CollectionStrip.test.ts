import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CollectionStrip from '@/components/CollectionStrip.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import type { CollectionDetail } from '@/types/api'

const RecommendationsRowStub = {
  props: { items: { type: Array, default: () => [] } },
  emits: ['status-changed'],
  template: '<div><span v-for="i in items" :key="i.id" class="part">{{ i.title }}</span></div>',
}

function buildCollection(): CollectionDetail {
  return {
    id: 10,
    name: 'Test Collection',
    overview: 'Overview',
    parts: [
      { id: 1, media_type: MEDIA_TYPE.MOVIE, title: 'Second', release_date: '2001-05-19' },
      { id: 2, media_type: MEDIA_TYPE.MOVIE, title: 'First', release_date: '1977-05-25' },
      { id: 3, media_type: MEDIA_TYPE.MOVIE, title: 'Undated', release_date: null },
    ],
  }
}

describe('CollectionStrip', () => {
  it('sorts parts by release date with undated last', () => {
    const wrapper = mount(CollectionStrip, {
      props: { collection: buildCollection() },
      global: { stubs: { RecommendationsRow: RecommendationsRowStub } },
    })
    expect(wrapper.findAll('.part').map((node) => node.text())).toEqual(['First', 'Second', 'Undated'])
  })

  it('patches the source part when a quick action changes status', async () => {
    const collection = buildCollection()
    const wrapper = mount(CollectionStrip, {
      props: { collection },
      global: { stubs: { RecommendationsRow: RecommendationsRowStub } },
    })
    const row = wrapper.findComponent(RecommendationsRowStub)
    row.vm.$emit('status-changed', {
      tmdb_id: 2,
      media_type: MEDIA_TYPE.MOVIE,
      status: 'plan_to_watch',
      watched_at: null,
      status_changed_at: '2026-01-01T00:00:00Z',
    })
    await wrapper.vm.$nextTick()
    expect(collection.parts.find((part) => part.id === 2)?.user_status?.status).toBe('plan_to_watch')
  })
})
