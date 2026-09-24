import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import PersonDetailView from '@/views/PersonDetailView.vue'
import type { PersonCredit } from '@/types/api'

const { getPerson, getPersonCredits } = vi.hoisted(() => ({
  getPerson: vi.fn(),
  getPersonCredits: vi.fn(),
}))

vi.mock('@/api', () => ({
  mediaAPI: { getPerson, getPersonCredits },
}))

function personPayload() {
  return { id: 34546, name: 'Mark Gatiss' }
}

function creditsPayload() {
  const crew: PersonCredit[] = Array.from({ length: 30 }, (_, index) => ({
    id: 1000 + index,
    media_type: 'movie',
    title: `Credit ${index}`,
    release_date: '2020-01-01',
    job: 'Writer',
  }))
  crew.push({
    id: 57243,
    media_type: 'tv',
    name: 'Doctor Who',
    first_credit_air_date: '2015-11-01',
    job: 'Writer',
  })
  return { cast: [], crew }
}

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/people/:id', name: 'person-detail', component: { template: '<div />' } },
      { path: '/movies/:id', name: 'movie-detail', component: { template: '<div />' } },
      { path: '/tv/:id', name: 'tv-detail', component: { template: '<div />' } },
    ],
  })
  await router.push('/people/34546')
  await router.isReady()

  const wrapper = mount(PersonDetailView, {
    global: {
      plugins: [router],
      stubs: {
        DetailHero: true,
        ExternalLinks: true,
        PersonKnownForScroller: true,
        PersonSidebar: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('PersonDetailView', () => {
  beforeEach(() => {
    getPerson.mockReset().mockResolvedValue(personPayload())
    getPersonCredits.mockReset().mockResolvedValue(creditsPayload())
  })

  it('renders crew credits beyond the first thirty entries', async () => {
    const wrapper = await mountView()

    expect(getPersonCredits).toHaveBeenCalledWith('34546')
    expect(wrapper.text()).toContain('Crew (31)')
    expect(wrapper.text()).toContain('Doctor Who')
    expect(wrapper.text()).toContain('Writer')
  })
})
