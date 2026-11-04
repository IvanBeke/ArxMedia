import { computed, onBeforeUnmount, ref, shallowRef } from 'vue'
import { useElementSize } from '@vueuse/core'
import {
  AVATAR_MAX_ZOOM,
  AVATAR_OUTPUT_SIZE,
  clampCrop,
  cropRect,
  initialCrop,
  panCrop,
  zoomCrop,
  type Anchor,
  type CropState,
  type ImageSize,
} from '@/utils/avatarCrop'

const KEY_PAN_STEP = 0.05
const KEY_ZOOM_FACTOR = 1.1
const WHEEL_ZOOM_SPEED = 0.002
const KEY_PAN: Record<string, [number, number]> = {
  ArrowLeft: [-KEY_PAN_STEP, 0],
  ArrowRight: [KEY_PAN_STEP, 0],
  ArrowUp: [0, -KEY_PAN_STEP],
  ArrowDown: [0, KEY_PAN_STEP],
}

interface Point { x: number; y: number }

function decodeImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => (img.naturalWidth && img.naturalHeight ? resolve(img) : reject(new Error('Image has no size')))
    img.onerror = () => reject(new Error('Image could not be decoded'))
    img.src = url
  })
}

export function useAvatarCrop() {
  const viewport = ref<HTMLElement | null>(null)
  const { width: viewportSize } = useElementSize(viewport)
  const source = shallowRef<HTMLImageElement | null>(null)
  const imageUrl = ref('')
  const crop = ref<CropState>({ zoom: 1, cx: 0, cy: 0 })
  const pointers = new Map<number, Point>()

  const image = computed<ImageSize | null>(() => source.value && { width: source.value.naturalWidth, height: source.value.naturalHeight })

  const imageStyle = computed(() => {
    if (!image.value) return {}
    const { width, height } = image.value
    const scale = (crop.value.zoom * viewportSize.value) / Math.min(width, height)
    const half = viewportSize.value / 2
    return {
      width: `${width * scale}px`,
      height: `${height * scale}px`,
      transform: `translate(${half - crop.value.cx * scale}px, ${half - crop.value.cy * scale}px)`,
    }
  })

  const zoom = computed({
    get: () => crop.value.zoom,
    set: (value: number) => {
      if (image.value) crop.value = zoomCrop(crop.value, image.value, value)
    },
  })

  function release() {
    pointers.clear()
    if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
    imageUrl.value = ''
    source.value = null
  }

  async function load(file: File) {
    release()
    const url = URL.createObjectURL(file)
    try {
      const decoded = await decodeImage(url)
      source.value = decoded
      imageUrl.value = url
      crop.value = initialCrop({ width: decoded.naturalWidth, height: decoded.naturalHeight })
    } catch (error) {
      URL.revokeObjectURL(url)
      throw error
    }
  }

  function anchorOf(point: Point): Anchor {
    const rect = viewport.value?.getBoundingClientRect()
    if (!rect || !rect.width || !rect.height) return { x: 0.5, y: 0.5 }
    return { x: (point.x - rect.left) / rect.width, y: (point.y - rect.top) / rect.height }
  }

  function viewportWidth(): number {
    return viewport.value?.getBoundingClientRect().width || 0
  }

  function onPointerDown(event: PointerEvent) {
    viewport.value?.setPointerCapture?.(event.pointerId)
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  }

  function onPointerMove(event: PointerEvent) {
    const previous = pointers.get(event.pointerId)
    const size = viewportWidth()
    if (!previous || !image.value || !size) return
    const current = { x: event.clientX, y: event.clientY }
    const other = [...pointers.entries()].find(([id]) => id !== event.pointerId)?.[1]

    if (!other) {
      crop.value = panCrop(crop.value, image.value, (current.x - previous.x) / size, (current.y - previous.y) / size)
    } else {
      const previousMid = { x: (previous.x + other.x) / 2, y: (previous.y + other.y) / 2 }
      const currentMid = { x: (current.x + other.x) / 2, y: (current.y + other.y) / 2 }
      const previousGap = Math.hypot(previous.x - other.x, previous.y - other.y)
      const currentGap = Math.hypot(current.x - other.x, current.y - other.y)
      const nextZoom = previousGap ? crop.value.zoom * (currentGap / previousGap) : crop.value.zoom
      const zoomed = zoomCrop(crop.value, image.value, nextZoom, anchorOf(previousMid))
      crop.value = panCrop(zoomed, image.value, (currentMid.x - previousMid.x) / size, (currentMid.y - previousMid.y) / size)
    }
    pointers.set(event.pointerId, current)
  }

  function onPointerEnd(event: PointerEvent) {
    pointers.delete(event.pointerId)
  }

  function onWheel(event: WheelEvent) {
    if (!image.value) return
    crop.value = zoomCrop(crop.value, image.value, crop.value.zoom * Math.exp(-event.deltaY * WHEEL_ZOOM_SPEED), anchorOf({ x: event.clientX, y: event.clientY }))
  }

  function onKeydown(event: KeyboardEvent) {
    if (!image.value) return
    const delta = KEY_PAN[event.key]
    if (delta) {
      crop.value = panCrop(crop.value, image.value, delta[0], delta[1])
    } else if (event.key === '+' || event.key === '=') {
      crop.value = zoomCrop(crop.value, image.value, crop.value.zoom * KEY_ZOOM_FACTOR)
    } else if (event.key === '-' || event.key === '_') {
      crop.value = zoomCrop(crop.value, image.value, crop.value.zoom / KEY_ZOOM_FACTOR)
    } else {
      return
    }
    event.preventDefault()
  }

  function exportBlob(): Promise<Blob> {
    const img = source.value
    const context = document.createElement('canvas').getContext('2d')
    if (!img || !image.value || !context) return Promise.reject(new Error('Nothing to export'))
    const canvas = context.canvas
    canvas.width = AVATAR_OUTPUT_SIZE
    canvas.height = AVATAR_OUTPUT_SIZE
    context.imageSmoothingQuality = 'high'
    const { sx, sy, size } = cropRect(clampCrop(crop.value, image.value), image.value)
    context.drawImage(img, sx, sy, size, size, 0, 0, AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE)
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Could not export the image'))), 'image/webp', 0.9)
    })
  }

  onBeforeUnmount(release)

  return {
    viewport, imageUrl, imageStyle, zoom, maxZoom: AVATAR_MAX_ZOOM,
    load, release, exportBlob,
    onPointerDown, onPointerMove, onPointerEnd, onWheel, onKeydown,
  }
}
