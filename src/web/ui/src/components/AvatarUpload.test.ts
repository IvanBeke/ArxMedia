import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { authAPI } from '@/api'
import AvatarUpload from '@/components/AvatarUpload.vue'
import { AVATAR_MAX_FILE_MB } from '@/utils/avatarCrop'
import type { User } from '@/types/api'

vi.mock('@/api', () => ({ authAPI: { uploadAvatar: vi.fn(), removeAvatar: vi.fn() } }))

class FakeImage {
  naturalWidth = 800
  naturalHeight = 400
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  set src(_value: string) {
    queueMicrotask(() => (FakeImage.fails ? this.onerror?.() : this.onload?.()))
  }
  static fails = false
}

const updatedUser = { id: 1, username: 'alex', avatar: '/media/avatars/x/avatar.webp' } as User
const png = new File(['x'], 'me.png', { type: 'image/png' })

function mountUpload(avatar: string | null = null) {
  return mount(AvatarUpload, { props: { username: 'alex', avatar }, attachTo: document.body })
}

async function chooseFile(wrapper: ReturnType<typeof mountUpload>, file: File) {
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  await flushPromises()
}

const dialogOpen = (wrapper: ReturnType<typeof mountUpload>) => (wrapper.get('dialog').element as HTMLDialogElement).open

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(authAPI.uploadAvatar).mockReset()
  vi.mocked(authAPI.removeAvatar).mockReset()
  FakeImage.fails = false
  vi.stubGlobal('Image', FakeImage)
  URL.createObjectURL = vi.fn(() => 'blob:photo')
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(function (this: HTMLCanvasElement) {
    return { canvas: this, drawImage: vi.fn(), imageSmoothingQuality: 'low' } as unknown as CanvasRenderingContext2D
  })
  HTMLCanvasElement.prototype.toBlob = (callback: BlobCallback) => callback(new Blob(['webp'], { type: 'image/webp' }))
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('AvatarUpload', () => {
  it('accepts only JPEG, PNG and WebP in the file picker', () => {
    expect(mountUpload().get('input[type="file"]').attributes('accept')).toBe('image/jpeg,image/png,image/webp')
  })

  it('only offers removal when there is a picture', () => {
    expect(mountUpload().text()).not.toContain('Remove photo')
    expect(mountUpload('/media/avatars/a/avatar.webp').text()).toContain('Remove photo')
  })

  it('opens the crop dialog for a chosen image', async () => {
    const wrapper = mountUpload()

    await chooseFile(wrapper, png)

    expect(dialogOpen(wrapper)).toBe(true)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('opens the crop dialog for a dropped image and highlights the zone while dragging', async () => {
    const wrapper = mountUpload()
    const zone = wrapper.get('label')

    await zone.trigger('dragenter')
    expect(wrapper.text()).toContain('Drop the photo to crop it')

    await zone.trigger('drop', { dataTransfer: { files: [png] } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Drop the photo to crop it')
    expect(dialogOpen(wrapper)).toBe(true)
  })

  it('ignores drops that carry no file', async () => {
    const wrapper = mountUpload()

    await wrapper.get('label').trigger('drop', { dataTransfer: { files: [] } })

    expect(dialogOpen(wrapper)).toBe(false)
  })

  it('rejects unsupported file types', async () => {
    const wrapper = mountUpload()

    await chooseFile(wrapper, new File(['x'], 'a.gif', { type: 'image/gif' }))

    expect(wrapper.get('[role="alert"]').text()).toBe('Choose a JPEG, PNG or WebP image.')
    expect(dialogOpen(wrapper)).toBe(false)
  })

  it('rejects oversized files', async () => {
    const wrapper = mountUpload()
    const big = new File(['x'], 'big.png', { type: 'image/png' })
    Object.defineProperty(big, 'size', { value: (AVATAR_MAX_FILE_MB + 1) * 1024 * 1024 })

    await chooseFile(wrapper, big)

    expect(wrapper.get('[role="alert"]').text()).toContain(`under ${AVATAR_MAX_FILE_MB} MB`)
    expect(dialogOpen(wrapper)).toBe(false)
  })

  it('reports images that cannot be decoded', async () => {
    FakeImage.fails = true
    const wrapper = mountUpload()

    await chooseFile(wrapper, png)

    expect(wrapper.get('[role="alert"]').text()).toContain('could not be opened')
    expect(dialogOpen(wrapper)).toBe(false)
  })

  it('uploads the cropped image, emits the updated user and closes the dialog', async () => {
    vi.mocked(authAPI.uploadAvatar).mockResolvedValue(updatedUser)
    const wrapper = mountUpload()
    await chooseFile(wrapper, png)

    await wrapper.findAll('dialog button').at(-1)?.trigger('click')
    await flushPromises()

    expect(authAPI.uploadAvatar).toHaveBeenCalledWith(expect.any(Blob))
    expect(wrapper.emitted('updated')?.[0]).toEqual([updatedUser])
    expect(dialogOpen(wrapper)).toBe(false)
  })

  it('keeps the dialog open and shows the server error when the upload fails', async () => {
    vi.mocked(authAPI.uploadAvatar).mockRejectedValue({ avatar: ['Image must be 5 MB or smaller.'], status: 400 })
    const wrapper = mountUpload()
    await chooseFile(wrapper, png)

    await wrapper.findAll('dialog button').at(-1)?.trigger('click')
    await flushPromises()

    expect(dialogOpen(wrapper)).toBe(true)
    expect(wrapper.get('dialog [role="alert"]').text()).toBe('Image must be 5 MB or smaller.')
    expect(wrapper.emitted('updated')).toBeUndefined()
  })

  it('removes the picture', async () => {
    vi.mocked(authAPI.removeAvatar).mockResolvedValue({ ...updatedUser, avatar: null })
    const wrapper = mountUpload('/media/avatars/a/avatar.webp')

    await wrapper.findAll('button').find((button) => button.text() === 'Remove photo')?.trigger('click')
    await flushPromises()

    expect(authAPI.removeAvatar).toHaveBeenCalledOnce()
    expect(wrapper.emitted('updated')?.[0]).toEqual([{ ...updatedUser, avatar: null }])
  })

  it('shows an error when removal fails', async () => {
    vi.mocked(authAPI.removeAvatar).mockRejectedValue({ status: 500 })
    const wrapper = mountUpload('/media/avatars/a/avatar.webp')

    await wrapper.findAll('button').find((button) => button.text() === 'Remove photo')?.trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('Failed to remove the profile picture')
  })
})
