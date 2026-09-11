import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import CalendarView from '@/views/CalendarView.vue'

const box = vi.hoisted(() => ({
  calendarGet: vi.fn(),
  mobile: null as unknown as { value: boolean },
  nowOverride: null as unknown as string | null,
}))

const isMobileRef = {
  get value(): boolean {
    return box.mobile?.value ?? false
  },
  set value(next: boolean) {
    if (box.mobile) box.mobile.value = next
  },
}

vi.mock('@/api', () => ({
  calendarAPI: { get: box.calendarGet },
}))

vi.mock('@vueuse/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@vueuse/core')>()
  const { ref } = await import('vue')
  if (!box.mobile) box.mobile = ref(false)
  return { ...actual, useMediaQuery: () => box.mobile }
})

vi.mock('@/utils/temporal', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/utils/temporal')>()
  return { ...actual, nowInstantIso: () => box.nowOverride ?? actual.nowInstantIso() }
})

const calendarGet = box.calendarGet

function episodeItem(date: string, showName = 'Test Show', airTime = '') {
  return {
    kind: 'episode',
    date,
    tmdb_id: 1399,
    show_name: showName,
    season_number: 1,
    episode_number: 2,
    episode_name: 'Pilot',
    air_time: airTime,
    poster_url: null,
  }
}

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', name: 'catch-all', component: { template: '<div />' } }],
  })
  await router.push({ path: '/calendar' })
  await router.isReady()

  const wrapper = mount(CalendarView, {
    global: {
      plugins: [router, createPinia()],
      stubs: { EpisodeCodePill: true },
    },
  })
  await flushPromises()
  return wrapper
}

function temporalNow() {
  const temporal = globalThis.Temporal
  if (!temporal) throw new Error('Temporal is unavailable in tests')
  return temporal
}

function todayKey() {
  return temporalNow().Now.plainDateISO().toString()
}

function lastCalendarParams() {
  const call = calendarGet.mock.calls.at(-1)
  if (!call || !call[0] || typeof call[0] !== 'object') throw new Error('Expected calendar API call')
  return call[0] as { start: string; days: number }
}

describe('CalendarView day/week/month', () => {
  beforeEach(() => {
    calendarGet.mockReset()
    calendarGet.mockResolvedValue({ results: [] })
    isMobileRef.value = false
    box.nowOverride = null
  })

  it('desktop shows day/week/month switcher and loads month range by default', async () => {
    const wrapper = await mountView()
    const switcher = wrapper.find('[aria-label="Calendar view mode"]')
    expect(switcher.exists()).toBe(true)
    expect(switcher.text()).toContain('Day')
    expect(switcher.text()).toContain('Week')
    expect(switcher.text()).toContain('Month')
    expect(calendarGet).toHaveBeenCalledTimes(1)
    const params = lastCalendarParams()
    expect(params.start).toMatch(/^\d{4}-\d{2}-01$/)
    expect(params.days).toBeGreaterThan(27)
  })

  it('desktop day mode requests a single day', async () => {
    const wrapper = await mountView()
    const dayButton = wrapper
      .findAll('[aria-label="Calendar view mode"] button')
      .find((b) => b.text() === 'Day')
    expect(dayButton).toBeTruthy()
    await dayButton!.trigger('click')
    await flushPromises()
    const last = lastCalendarParams()
    expect(last.days).toBe(1)
    expect(todayKey()).toContain(last.start.slice(0, 7))
  })

  it('mobile forces day view, hides switcher, and requests days=1', async () => {
    isMobileRef.value = true
    calendarGet.mockResolvedValueOnce({ results: [] })
    const wrapper = await mountView()
    expect(wrapper.find('[aria-label="Calendar view mode"]').classes()).toContain('hidden')
    expect(wrapper.find('[aria-label="Previous day"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Nothing scheduled for this day.')
    const params = lastCalendarParams()
    expect(params.days).toBe(1)
    expect(params.start).toBe(todayKey())
  })

  it('mobile day view renders items and prev/next shift by one day', async () => {
    isMobileRef.value = true
    const today = todayKey()
    calendarGet.mockResolvedValue({ results: [episodeItem(today)] })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Test Show')

    await wrapper.find('[aria-label="Next day"]').trigger('click')
    await flushPromises()
    const nextParams = lastCalendarParams()
    expect(nextParams.days).toBe(1)
    expect(nextParams.start).toBe(temporalNow().PlainDate.from(today).add({ days: 1 }).toString())

    await wrapper.find('[aria-label="Previous day"]').trigger('click')
    await flushPromises()
    const prevParams = lastCalendarParams()
    expect(prevParams.start).toBe(today)
  })

  it('surfaces API errors as an empty day without crashing', async () => {
    isMobileRef.value = true
    calendarGet.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Nothing scheduled for this day.')
  })

  it('groups broadcast datetime episodes onto their plain-date day cell', async () => {
    box.nowOverride = '2026-09-12T12:00:00+02:00'
    calendarGet.mockResolvedValue({
      results: [episodeItem('2026-09-12T16:00:00+02:00', 'Broadcast Show')],
    })
    const wrapper = await mountView()
    // Month grid: the 2026-09-12 cell must contain the broadcast episode.
    expect(wrapper.text()).toContain('Broadcast Show')
    expect(lastCalendarParams().start).toBe('2026-09-01')
  })

  it('mobile day view shows broadcast datetime episodes for the current day', async () => {
    box.nowOverride = '2026-09-12T12:00:00+02:00'
    isMobileRef.value = true
    calendarGet.mockResolvedValue({ results: [episodeItem('2026-09-12T16:00:00+02:00', 'Broadcast Show')] })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Broadcast Show')
    expect(wrapper.text()).not.toContain('Nothing scheduled for this day.')
    expect(lastCalendarParams()).toEqual({ start: '2026-09-12', days: 1 })
  })

  it('displays the release time next to the episode code', async () => {
    box.nowOverride = '2026-09-12T12:00:00+02:00'
    isMobileRef.value = true
    calendarGet.mockResolvedValue({
      results: [episodeItem('2026-09-12T16:00:00+02:00', 'Timed Show', '16:00')],
    })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('16:00')
  })

  it('hides the release time when the episode has no broadcast time', async () => {
    box.nowOverride = '2026-09-12T12:00:00+02:00'
    isMobileRef.value = true
    calendarGet.mockResolvedValue({
      results: [episodeItem('2026-09-12', 'Dateless Show')],
    })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('Dateless Show')
    expect(wrapper.text()).not.toMatch(/\d{2}:\d{2}/)
  })
})
