import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import AddToSonarrDialog from '@/components/AddToSonarrDialog.vue'

const { getSonarrSeries, getSonarrOptions, addSonarrSeries, removeSonarrSeries } = vi.hoisted(() => ({
  getSonarrSeries: vi.fn(),
  getSonarrOptions: vi.fn(),
  addSonarrSeries: vi.fn(),
  removeSonarrSeries: vi.fn(),
}))

vi.mock('@/api', () => ({ integrationsAPI: { getSonarrSeries, getSonarrOptions, addSonarrSeries, removeSonarrSeries } }))

const OPTIONS = {
  root_folders: [
    { path: '/tv', free_space: 5 * 1024 ** 3 },
    { path: '/anime', free_space: null },
  ],
  quality_profiles: [{ id: 4, name: 'HD-1080p' }, { id: 7, name: 'Ultra-HD' }],
  tags: [{ id: 2, label: 'kids' }],
}

async function openDialog() {
  const wrapper = mount(AddToSonarrDialog, { props: { tmdbId: 1396, title: 'Breaking Bad' } })
  wrapper.vm.showModal()
  await flushPromises()
  return wrapper
}

describe('AddToSonarrDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getSonarrSeries.mockResolvedValue({ added: false })
    getSonarrOptions.mockResolvedValue(OPTIONS)
    addSonarrSeries.mockResolvedValue({ added: true, path: '/tv/Breaking Bad', monitored: true })
  })

  it('loads state and options when opened and preselects the first choices', async () => {
    const wrapper = await openDialog()

    expect(wrapper.find('dialog').element.open).toBe(true)
    expect(getSonarrSeries).toHaveBeenCalledWith(1396, expect.any(Object))
    expect(wrapper.text()).toContain('Breaking Bad')
    const selects = wrapper.findAll('select')
    expect(selects[0]?.element.value).toBe('4')
    expect(selects[1]?.element.value).toBe('/tv')
    expect(selects[1]?.text()).toContain('/tv (5 GB free)')
    expect(selects[2]?.element.value).toBe('standard')
    expect(selects[3]?.element.value).toBe('all')
  })

  it('shows the series fields and none of the movie ones', async () => {
    const wrapper = await openDialog()

    for (const label of ['Series type', 'Monitor', 'Monitored', 'Use season folders', 'Search for missing episodes after adding']) {
      expect(wrapper.text()).toContain(label)
    }
    expect(wrapper.text()).not.toContain('Minimum availability')
  })

  it('titles the dialog after what it is showing', async () => {
    const wrapper = await openDialog()
    expect(wrapper.get('h2').text()).toBe('Add to Sonarr')

    getSonarrSeries.mockResolvedValue({ added: true, path: '/s', monitored: true })
    wrapper.vm.showModal()
    await flushPromises()
    expect(wrapper.get('h2').text()).toBe('In Sonarr')

    await wrapper.findAll('button').find((button) => button.text() === 'Remove from Sonarr')!.trigger('click')
    expect(wrapper.get('h2').text()).toBe('Remove from Sonarr')
  })

  it('submits the chosen settings, emits added and closes', async () => {
    const wrapper = await openDialog()
    await wrapper.findAll('select')[0]!.setValue('7')
    await wrapper.findAll('select')[2]!.setValue('anime')
    await wrapper.findAll('select')[3]!.setValue('firstSeason')
    await wrapper.get('input[type="checkbox"][value="2"]').setValue(true)
    await wrapper.findAll('input[type="checkbox"]').at(-2)!.setValue(false)

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(addSonarrSeries).toHaveBeenCalledWith(1396, {
      quality_profile_id: 7,
      root_folder_path: '/tv',
      series_type: 'anime',
      monitor: 'firstSeason',
      monitored: true,
      season_folder: false,
      search_for_missing_episodes: true,
      tags: [2],
    })
    expect(wrapper.emitted('added')).toHaveLength(1)
    expect(wrapper.find('dialog').element.open).toBe(false)
  })

  it('reports the series state it loaded and the state after adding', async () => {
    const wrapper = await openDialog()
    expect(wrapper.emitted('synced')?.[0]).toEqual([{ added: false }])

    addSonarrSeries.mockResolvedValue({ added: true, url: 'https://sonarr.example.com/series/breaking-bad' })
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('synced')?.[1]).toEqual([{ added: true, url: 'https://sonarr.example.com/series/breaking-bad' }])
  })

  describe('when the show is already in Sonarr', () => {
    const IN_SONARR = { added: true, path: '/tv/Breaking Bad', monitored: true, url: 'https://sonarr.example.com/series/breaking-bad' }

    function button(wrapper: Awaited<ReturnType<typeof openDialog>>, label: string) {
      return wrapper.findAll('button').find((candidate) => candidate.text() === label)
    }

    beforeEach(() => {
      getSonarrSeries.mockResolvedValue(IN_SONARR)
      removeSonarrSeries.mockResolvedValue({ added: false })
    })

    it('shows the existing path instead of the form', async () => {
      const wrapper = await openDialog()

      expect(wrapper.text()).toContain('This show is already in Sonarr.')
      expect(wrapper.text()).toContain('/tv/Breaking Bad')
      expect(wrapper.find('form').exists()).toBe(false)
    })

    it('offers to open the show in a new tab or remove it', async () => {
      const wrapper = await openDialog()

      const link = wrapper.get('a')
      expect(link.text()).toBe('Open in Sonarr')
      expect(link.attributes('href')).toBe(IN_SONARR.url)
      expect(link.attributes('target')).toBe('_blank')
      expect(link.attributes('rel')).toContain('noopener')
      expect(button(wrapper, 'Remove from Sonarr')).toBeTruthy()
    })

    it('removes the show with the chosen options after confirmation', async () => {
      const wrapper = await openDialog()
      await button(wrapper, 'Remove from Sonarr')!.trigger('click')
      expect(removeSonarrSeries).not.toHaveBeenCalled()
      expect(wrapper.text()).toContain('Remove this show from Sonarr?')

      const [deleteFiles, exclusion] = wrapper.findAll('input[type="checkbox"]')
      expect((deleteFiles!.element as HTMLInputElement).checked).toBe(false)
      await deleteFiles!.setValue(true)
      await exclusion!.setValue(true)
      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(removeSonarrSeries).toHaveBeenCalledWith(1396, { delete_files: true, add_import_exclusion: true })
      expect(wrapper.emitted('removed')).toHaveLength(1)
      expect(wrapper.emitted('synced')?.at(-1)).toEqual([{ added: false }])
      expect(wrapper.find('dialog').element.open).toBe(false)
    })

    it('shows the error and stays on the confirmation when removing fails', async () => {
      removeSonarrSeries.mockRejectedValueOnce({ detail: 'Series is locked', status: 400 })
      const wrapper = await openDialog()
      await button(wrapper, 'Remove from Sonarr')!.trigger('click')

      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(wrapper.get('form [role="alert"]').text()).toBe('Series is locked')
      expect(wrapper.emitted('removed')).toBeUndefined()
    })

    it('reloads the state when the show is already gone from Sonarr', async () => {
      removeSonarrSeries.mockRejectedValueOnce({ detail: 'Series is not in Sonarr.', status: 404 })
      const wrapper = await openDialog()
      await button(wrapper, 'Remove from Sonarr')!.trigger('click')
      getSonarrSeries.mockResolvedValue({ added: false })

      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Quality profile')
    })
  })

  it('shows a retryable error when loading fails', async () => {
    getSonarrOptions.mockRejectedValueOnce({ detail: 'This show has no TheTVDB id, which Sonarr needs.', status: 422 })

    const wrapper = await openDialog()

    expect(wrapper.get('[role="alert"]').text()).toContain('no TheTVDB id')
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(getSonarrOptions).toHaveBeenCalledTimes(2)
    expect(wrapper.find('form').exists()).toBe(true)
  })

  it('keeps the dialog open and shows the error when adding fails', async () => {
    addSonarrSeries.mockRejectedValueOnce({ detail: 'Folder is not writable', status: 400 })
    const wrapper = await openDialog()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('form [role="alert"]').text()).toBe('Folder is not writable')
    expect(wrapper.emitted('added')).toBeUndefined()
    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('switches to the already-added state when Sonarr reports a conflict', async () => {
    addSonarrSeries.mockRejectedValueOnce({ detail: 'Series is already in Sonarr.', status: 409 })
    const wrapper = await openDialog()
    getSonarrSeries.mockResolvedValue({ added: true, path: '/tv/Breaking Bad', monitored: true })

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('already in Sonarr')
  })

  it('disables submit when Sonarr has no root folders or quality profiles', async () => {
    getSonarrOptions.mockResolvedValue({ root_folders: [], quality_profiles: [], tags: [] })

    const wrapper = await openDialog()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })
})
