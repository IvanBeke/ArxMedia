import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ArrRemoveForm from '@/components/ArrRemoveForm.vue'

const PROPS = { message: 'Remove this movie from Radarr?', deleteFilesLabel: 'Delete movie files' }

describe('ArrRemoveForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the message and both options, unchecked by default', () => {
    const wrapper = mount(ArrRemoveForm, { props: PROPS })

    expect(wrapper.text()).toContain('Remove this movie from Radarr?')
    expect(wrapper.text()).toContain('Delete movie files')
    expect(wrapper.text()).toContain('Add import list exclusion')
    const boxes = wrapper.findAll('input[type="checkbox"]').map((box) => (box.element as HTMLInputElement).checked)
    expect(boxes).toEqual([false, false])
  })

  it('submits the chosen options', async () => {
    const wrapper = mount(ArrRemoveForm, { props: PROPS })
    const [deleteFiles, exclusion] = wrapper.findAll('input[type="checkbox"]')
    await deleteFiles!.setValue(true)
    await exclusion!.setValue(true)

    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')).toEqual([[{ delete_files: true, add_import_exclusion: true }]])
  })

  it('goes back without submitting', async () => {
    const wrapper = mount(ArrRemoveForm, { props: PROPS })

    await wrapper.findAll('button').find((button) => button.text() === 'Back')!.trigger('click')

    expect(wrapper.emitted('back')).toHaveLength(1)
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('disables the buttons and says so while submitting', () => {
    const wrapper = mount(ArrRemoveForm, { props: { ...PROPS, submitting: true } })

    expect(wrapper.text()).toContain('Removing...')
    expect(wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined)).toBe(true)
  })

  it('shows an error', () => {
    const wrapper = mount(ArrRemoveForm, { props: { ...PROPS, error: 'Movie is locked' } })

    expect(wrapper.get('[role="alert"]').text()).toBe('Movie is locked')
  })
})
