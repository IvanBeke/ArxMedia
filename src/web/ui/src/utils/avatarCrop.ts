export const AVATAR_OUTPUT_SIZE = 512
export const AVATAR_MAX_ZOOM = 4
export const AVATAR_MAX_FILE_MB = 20
export const AVATAR_ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export interface ImageSize { width: number; height: number }
/** `zoom` is relative to the smallest zoom that still covers the circle (1 = the shorter side fits). `cx`/`cy` is the image point at the circle's centre, in natural pixels. */
export interface CropState { zoom: number; cx: number; cy: number }
export interface CropRect { sx: number; sy: number; size: number }
export interface Anchor { x: number; y: number }

const CENTER: Anchor = { x: 0.5, y: 0.5 }

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

/** Side of the square source region, in natural pixels, visible at this zoom. */
export function cropSize(image: ImageSize, zoom: number): number {
  return Math.min(image.width, image.height) / zoom
}

export function initialCrop(image: ImageSize): CropState {
  return { zoom: 1, cx: image.width / 2, cy: image.height / 2 }
}

/** Keeps the zoom in range and the crop square inside the image, so the circle is never empty. */
export function clampCrop(crop: CropState, image: ImageSize): CropState {
  const zoom = clamp(crop.zoom, 1, AVATAR_MAX_ZOOM)
  const half = cropSize(image, zoom) / 2
  return {
    zoom,
    cx: clamp(crop.cx, half, image.width - half),
    cy: clamp(crop.cy, half, image.height - half),
  }
}

/** Moves the image by a distance given in fractions of the circle's diameter. */
export function panCrop(crop: CropState, image: ImageSize, dx: number, dy: number): CropState {
  const size = cropSize(image, crop.zoom)
  return clampCrop({ ...crop, cx: crop.cx - dx * size, cy: crop.cy - dy * size }, image)
}

/** Zooms while keeping the image point under `anchor` (fractions of the circle's box) fixed. */
export function zoomCrop(crop: CropState, image: ImageSize, zoom: number, anchor: Anchor = CENTER): CropState {
  const next = clamp(zoom, 1, AVATAR_MAX_ZOOM)
  const before = cropSize(image, crop.zoom)
  const after = cropSize(image, next)
  return clampCrop({
    zoom: next,
    cx: crop.cx + (anchor.x - 0.5) * (before - after),
    cy: crop.cy + (anchor.y - 0.5) * (before - after),
  }, image)
}

export function cropRect(crop: CropState, image: ImageSize): CropRect {
  const size = cropSize(image, crop.zoom)
  return { sx: crop.cx - size / 2, sy: crop.cy - size / 2, size }
}

export type AvatarFileError = 'type' | 'size'

export function avatarFileError(file: Pick<File, 'type' | 'size'>): AvatarFileError | null {
  if (!AVATAR_ACCEPTED_TYPES.includes(file.type)) return 'type'
  if (file.size > AVATAR_MAX_FILE_MB * 1024 * 1024) return 'size'
  return null
}
