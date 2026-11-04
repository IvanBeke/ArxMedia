import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import AvatarCropDialog from '@/components/AvatarCropDialog.vue'
import { required } from '@/test-support/assertions'

// A 800x400 photo: the circle initially shows the central 400x400 square.
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

const drawImage = vi.fn()
const file = new File(['x'], 'me.png', { type: 'image/png' })

function mountDialog(props: { saving?: boolean; error?: string } = {}) {
  const wrapper = mount(AvatarCropDialog, { props: { saving: false, error: '', ...props }, attachTo: document.body })
  const viewport = wrapper.get('[role="group"]')
  vi.spyOn(viewport.element, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 200, height: 200, right: 200, bottom: 200, x: 0, y: 0, toJSON: () => ({}) })
  return { wrapper, viewport }
}

async function savedRect(wrapper: ReturnType<typeof mountDialog>['wrapper']) {
  drawImage.mockClear()
  await wrapper.findAll('button').at(-1)?.trigger('click')
  await flushPromises()
  const [, sx, sy, size, , dx, dy, outW, outH] = required(drawImage.mock.calls[0], 'drawImage call')
  return { sx, sy, size, dx, dy, outW, outH }
}

// jsdom has no PointerEvent and VTU cannot set clientX, so dispatch real events by hand.
function firePointer(target: Element, type: string, pointerId: number, clientX: number, clientY: number) {
  const event = new MouseEvent(type, { clientX, clientY, bubbles: true })
  Object.defineProperty(event, 'pointerId', { value: pointerId })
  target.dispatchEvent(event)
}

function fireWheel(target: Element, deltaY: number, clientX: number, clientY: number) {
  target.dispatchEvent(new WheelEvent('wheel', { deltaY, clientX, clientY, bubbles: true, cancelable: true }))
}

beforeEach(() => {
  setActivePinia(createPinia())
  FakeImage.fails = false
  vi.stubGlobal('Image', FakeImage)
  URL.createObjectURL = vi.fn(() => 'blob:photo')
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(function (this: HTMLCanvasElement) {
    return { canvas: this, drawImage, imageSmoothingQuality: 'low' } as unknown as CanvasRenderingContext2D
  })
  HTMLCanvasElement.prototype.toBlob = (callback: BlobCallback) => callback(new Blob(['webp'], { type: 'image/webp' }))
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('AvatarCropDialog', () => {
  it('opens as a modal once the image has loaded', async () => {
    const { wrapper } = mountDialog()
    await wrapper.vm.open(file)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('dialog').element.open).toBe(true)
    expect(wrapper.get('img').attributes('src')).toBe('blob:photo')
  })

  it('rejects and stays closed when the image cannot be decoded', async () => {
    FakeImage.fails = true
    const { wrapper } = mountDialog()

    await expect(wrapper.vm.open(file)).rejects.toThrow()

    expect(wrapper.find('dialog').element.open).toBe(false)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:photo')
  })

  it('exports the centred square at 512x512 by default', async () => {
    const { wrapper } = mountDialog()
    await wrapper.vm.open(file)

    expect(await savedRect(wrapper)).toEqual({ sx: 200, sy: 0, size: 400, dx: 0, dy: 0, outW: 512, outH: 512 })
    expect(wrapper.emitted('save')?.[0]?.[0]).toBeInstanceOf(Blob)
  })

  it('pans with a pointer drag', async () => {
    const { wrapper, viewport } = mountDialog()
    await wrapper.vm.open(file)

    firePointer(viewport.element, 'pointerdown', 1, 100, 100)
    firePointer(viewport.element, 'pointermove', 1, 150, 100)
    firePointer(viewport.element, 'pointerup', 1, 150, 100)

    expect(await savedRect(wrapper)).toMatchObject({ sx: 100, sy: 0, size: 400 })
  })

  it('keeps panning inside the photo', async () => {
    const { wrapper, viewport } = mountDialog()
    await wrapper.vm.open(file)

    firePointer(viewport.element, 'pointerdown', 1, 0, 0)
    firePointer(viewport.element, 'pointermove', 1, 5000, 5000)

    expect(await savedRect(wrapper)).toMatchObject({ sx: 0, sy: 0, size: 400 })
  })

  it('zooms with the slider', async () => {
    const { wrapper } = mountDialog()
    await wrapper.vm.open(file)

    await wrapper.get('input[type="range"]').setValue('2')

    expect(await savedRect(wrapper)).toMatchObject({ sx: 300, sy: 100, size: 200 })
  })

  it('zooms with the mouse wheel', async () => {
    const { wrapper, viewport } = mountDialog()
    await wrapper.vm.open(file)

    fireWheel(viewport.element, -500, 100, 100)

    expect((await savedRect(wrapper)).size).toBeLessThan(400)
  })

  it('zooms with a two-finger pinch', async () => {
    const { wrapper, viewport } = mountDialog()
    await wrapper.vm.open(file)

    firePointer(viewport.element, 'pointerdown', 1, 50, 100)
    firePointer(viewport.element, 'pointerdown', 2, 150, 100)
    firePointer(viewport.element, 'pointermove', 1, 0, 100)
    firePointer(viewport.element, 'pointermove', 2, 200, 100)

    expect((await savedRect(wrapper)).size).toBeCloseTo(200)
  })

  it('supports keyboard panning and zooming', async () => {
    const { wrapper, viewport } = mountDialog()
    await wrapper.vm.open(file)

    await viewport.trigger('keydown', { key: 'ArrowRight' })
    expect(await savedRect(wrapper)).toMatchObject({ sx: 180, size: 400 })

    await viewport.trigger('keydown', { key: '+' })
    expect((await savedRect(wrapper)).size).toBeLessThan(400)
  })

  it('shows the upload error and disables saving while saving', async () => {
    const { wrapper } = mountDialog({ error: 'Upload failed', saving: true })

    expect(wrapper.get('[role="alert"]').text()).toBe('Upload failed')
    expect(wrapper.findAll('button').at(-1)?.attributes('disabled')).toBeDefined()
  })

  it('reports an export failure', async () => {
    HTMLCanvasElement.prototype.toBlob = (callback: BlobCallback) => callback(null)
    const { wrapper } = mountDialog()
    await wrapper.vm.open(file)

    await wrapper.findAll('button').at(-1)?.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('could not be opened')
  })

  it('frees the object URL when closed', async () => {
    const { wrapper } = mountDialog()
    await wrapper.vm.open(file)

    wrapper.vm.close()
    await wrapper.get('dialog').trigger('close')

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:photo')
  })
})
