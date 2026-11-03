import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import AddToRadarrDialog from '@/components/AddToRadarrDialog.vue'

const { getRadarrMovie, getRadarrOptions, addRadarrMovie, removeRadarrMovie } = vi.hoisted(() => ({
  getRadarrMovie: vi.fn(),
  getRadarrOptions: vi.fn(),
  addRadarrMovie: vi.fn(),
  removeRadarrMovie: vi.fn(),
}))

vi.mock('@/api', () => ({ integrationsAPI: { getRadarrMovie, getRadarrOptions, addRadarrMovie, removeRadarrMovie } }))

const OPTIONS = {
  root_folders: [
    { path: '/movies', free_space: 5 * 1024 ** 3 },
    { path: '/4k', free_space: null },
  ],
  quality_profiles: [{ id: 4, name: 'HD-1080p' }, { id: 7, name: 'Ultra-HD' }],
  tags: [{ id: 2, label: 'kids' }],
}

async function openDialog() {
  const wrapper = mount(AddToRadarrDialog, { props: { tmdbId: 603, title: 'The Matrix' } })
  wrapper.vm.showModal()
  await flushPromises()
  return wrapper
}

describe('AddToRadarrDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getRadarrMovie.mockResolvedValue({ added: false })
    getRadarrOptions.mockResolvedValue(OPTIONS)
    addRadarrMovie.mockResolvedValue({ added: true, path: '/movies/The Matrix (1999)', monitored: true })
  })

  it('loads state and options when opened and preselects the first choices', async () => {
    const wrapper = await openDialog()

    expect(wrapper.find('dialog').element.open).toBe(true)
    expect(getRadarrMovie).toHaveBeenCalledWith(603, expect.any(Object))
    expect(wrapper.text()).toContain('The Matrix')
    const selects = wrapper.findAll('select')
    expect(selects[0]?.element.value).toBe('4')
    expect(selects[1]?.element.value).toBe('/movies')
    expect(selects[1]?.text()).toContain('/movies (5 GB free)')
  })

  it('titles the dialog after what it is showing', async () => {
    const wrapper = await openDialog()
    expect(wrapper.get('h2').text()).toBe('Add to Radarr')

    getRadarrMovie.mockResolvedValue({ added: true, path: '/m', monitored: true })
    wrapper.vm.showModal()
    await flushPromises()
    expect(wrapper.get('h2').text()).toBe('In Radarr')

    await wrapper.findAll('button').find((button) => button.text() === 'Remove from Radarr')!.trigger('click')
    expect(wrapper.get('h2').text()).toBe('Remove from Radarr')
  })

  it('submits the chosen settings, emits added and closes', async () => {
    const wrapper = await openDialog()
    await wrapper.findAll('select')[0]!.setValue('7')
    await wrapper.findAll('select')[2]!.setValue('inCinemas')
    await wrapper.get('input[type="checkbox"][value="2"]').setValue(true)
    await wrapper.findAll('input[type="checkbox"]').at(-1)!.setValue(false)

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(addRadarrMovie).toHaveBeenCalledWith(603, {
      quality_profile_id: 7,
      root_folder_path: '/movies',
      minimum_availability: 'inCinemas',
      monitored: true,
      search_for_movie: false,
      tags: [2],
    })
    expect(wrapper.emitted('added')).toHaveLength(1)
    expect(wrapper.find('dialog').element.open).toBe(false)
  })

  it('reports the movie state it loaded and the state after adding', async () => {
    const wrapper = await openDialog()
    expect(wrapper.emitted('synced')?.[0]).toEqual([{ added: false }])

    addRadarrMovie.mockResolvedValue({ added: true, url: 'https://radarr.example.com/movie/603' })
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('synced')?.[1]).toEqual([{ added: true, url: 'https://radarr.example.com/movie/603' }])
  })

  it('shows the existing path instead of the form when the movie is already added', async () => {
    getRadarrMovie.mockResolvedValue({ added: true, path: '/movies/The Matrix (1999)', monitored: true })

    const wrapper = await openDialog()

    expect(wrapper.text()).toContain('already in Radarr')
    expect(wrapper.text()).toContain('/movies/The Matrix (1999)')
    expect(wrapper.find('form').exists()).toBe(false)
  })

  describe('when the movie is already in Radarr', () => {
    const IN_RADARR = { added: true, path: '/movies/The Matrix (1999)', monitored: true, url: 'https://radarr.example.com/movie/the-matrix-603' }

    function button(wrapper: Awaited<ReturnType<typeof openDialog>>, label: string) {
      return wrapper.findAll('button').find((candidate) => candidate.text() === label)
    }

    beforeEach(() => {
      getRadarrMovie.mockResolvedValue(IN_RADARR)
      removeRadarrMovie.mockResolvedValue({ added: false })
    })

    it('offers to open the movie in a new tab or remove it', async () => {
      const wrapper = await openDialog()

      const link = wrapper.get('a')
      expect(link.text()).toBe('Open in Radarr')
      expect(link.attributes('href')).toBe(IN_RADARR.url)
      expect(link.attributes('target')).toBe('_blank')
      expect(link.attributes('rel')).toContain('noopener')
      expect(button(wrapper, 'Remove from Radarr')).toBeTruthy()
    })

    it('omits the open link when Radarr gave no URL', async () => {
      getRadarrMovie.mockResolvedValue({ added: true, path: '/m', monitored: true })

      const wrapper = await openDialog()

      expect(wrapper.find('a').exists()).toBe(false)
    })

    it('removes the movie with the chosen options after confirmation', async () => {
      const wrapper = await openDialog()
      await button(wrapper, 'Remove from Radarr')!.trigger('click')
      expect(removeRadarrMovie).not.toHaveBeenCalled()

      const [deleteFiles, exclusion] = wrapper.findAll('input[type="checkbox"]')
      expect((deleteFiles!.element as HTMLInputElement).checked).toBe(false)
      await deleteFiles!.setValue(true)
      await exclusion!.setValue(true)
      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(removeRadarrMovie).toHaveBeenCalledWith(603, { delete_files: true, add_import_exclusion: true })
      expect(wrapper.emitted('removed')).toHaveLength(1)
      expect(wrapper.emitted('synced')?.at(-1)).toEqual([{ added: false }])
      expect(wrapper.find('dialog').element.open).toBe(false)
    })

    it('goes back to the choices without removing', async () => {
      const wrapper = await openDialog()
      await button(wrapper, 'Remove from Radarr')!.trigger('click')

      await button(wrapper, 'Back')!.trigger('click')

      expect(removeRadarrMovie).not.toHaveBeenCalled()
      expect(wrapper.find('a').exists()).toBe(true)
    })

    it('shows the error and stays on the confirmation when removing fails', async () => {
      removeRadarrMovie.mockRejectedValueOnce({ detail: 'Movie is locked', status: 400 })
      const wrapper = await openDialog()
      await button(wrapper, 'Remove from Radarr')!.trigger('click')

      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(wrapper.get('form [role="alert"]').text()).toBe('Movie is locked')
      expect(wrapper.emitted('removed')).toBeUndefined()
    })

    it('reloads the state when the movie is already gone from Radarr', async () => {
      removeRadarrMovie.mockRejectedValueOnce({ detail: 'Movie is not in Radarr.', status: 404 })
      const wrapper = await openDialog()
      await button(wrapper, 'Remove from Radarr')!.trigger('click')
      getRadarrMovie.mockResolvedValue({ added: false })

      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('Quality profile')
    })
  })

  it('shows a retryable error when loading fails', async () => {
    getRadarrOptions.mockRejectedValueOnce({ detail: 'Could not reach Radarr.', status: 502 })

    const wrapper = await openDialog()

    expect(wrapper.get('[role="alert"]').text()).toContain('Could not reach Radarr.')
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(getRadarrOptions).toHaveBeenCalledTimes(2)
    expect(wrapper.find('form').exists()).toBe(true)
  })

  it('keeps the dialog open and shows the error when adding fails', async () => {
    addRadarrMovie.mockRejectedValueOnce({ detail: 'Folder is not writable', status: 400 })
    const wrapper = await openDialog()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('form [role="alert"]').text()).toBe('Folder is not writable')
    expect(wrapper.emitted('added')).toBeUndefined()
    expect(wrapper.find('dialog').element.open).toBe(true)
  })

  it('switches to the already-added state when Radarr reports a conflict', async () => {
    addRadarrMovie.mockRejectedValueOnce({ detail: 'Movie is already in Radarr.', status: 409 })
    const wrapper = await openDialog()
    getRadarrMovie.mockResolvedValue({ added: true, path: '/movies/The Matrix (1999)', monitored: true })

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('already in Radarr')
  })

  it('disables submit when Radarr has no root folders or quality profiles', async () => {
    getRadarrOptions.mockResolvedValue({ root_folders: [], quality_profiles: [], tags: [] })

    const wrapper = await openDialog()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })
})
