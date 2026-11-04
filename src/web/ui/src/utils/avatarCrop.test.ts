import { describe, expect, it } from 'vitest'
import {
  AVATAR_MAX_FILE_MB,
  AVATAR_MAX_ZOOM,
  avatarFileError,
  clampCrop,
  cropRect,
  cropSize,
  initialCrop,
  panCrop,
  zoomCrop,
} from '@/utils/avatarCrop'

const wide = { width: 800, height: 400 }
const tall = { width: 300, height: 600 }

describe('avatarCrop', () => {
  it('starts centred with the shorter side filling the circle', () => {
    expect(initialCrop(wide)).toEqual({ zoom: 1, cx: 400, cy: 200 })
    expect(cropRect(initialCrop(wide), wide)).toEqual({ sx: 200, sy: 0, size: 400 })
    expect(cropRect(initialCrop(tall), tall)).toEqual({ sx: 0, sy: 150, size: 300 })
  })

  it('shrinks the visible region as zoom grows', () => {
    expect(cropSize(wide, 2)).toBe(200)
    expect(cropSize(wide, AVATAR_MAX_ZOOM)).toBe(100)
  })

  it('clamps zoom and keeps the crop square inside the image', () => {
    expect(clampCrop({ zoom: 0.2, cx: 400, cy: 200 }, wide).zoom).toBe(1)
    expect(clampCrop({ zoom: 99, cx: 400, cy: 200 }, wide).zoom).toBe(AVATAR_MAX_ZOOM)
    expect(clampCrop({ zoom: 1, cx: -50, cy: 900 }, wide)).toEqual({ zoom: 1, cx: 200, cy: 200 })
    expect(clampCrop({ zoom: 2, cx: 0, cy: 0 }, wide)).toEqual({ zoom: 2, cx: 100, cy: 100 })
  })

  it('pans the photo with the pointer and stops at the image edge', () => {
    const panned = panCrop(initialCrop(wide), wide, 0.25, 0)
    expect(panned.cx).toBe(300)
    expect(panCrop(initialCrop(wide), wide, 5, 0).cx).toBe(200)
    expect(panCrop(initialCrop(wide), wide, 0, 5).cy).toBe(200)
  })

  it('zooms around the anchor so the point under it stays put', () => {
    const start = { zoom: 1, cx: 400, cy: 200 }
    const anchor = { x: 0.75, y: 0.5 }
    const pointBefore = start.cx + (anchor.x - 0.5) * cropSize(wide, start.zoom)

    const zoomed = zoomCrop(start, wide, 2, anchor)
    const pointAfter = zoomed.cx + (anchor.x - 0.5) * cropSize(wide, zoomed.zoom)

    expect(zoomed.zoom).toBe(2)
    expect(pointAfter).toBeCloseTo(pointBefore)
  })

  it('zooms around the centre by default and refuses to leave the image', () => {
    expect(zoomCrop(initialCrop(wide), wide, 2)).toEqual({ zoom: 2, cx: 400, cy: 200 })
    const corner = zoomCrop({ zoom: 1, cx: 200, cy: 200 }, wide, 4, { x: 0, y: 0 })
    expect(cropRect(corner, wide).sx).toBeGreaterThanOrEqual(0)
    expect(cropRect(corner, wide).sy).toBeGreaterThanOrEqual(0)
  })

  it('validates file type and size', () => {
    expect(avatarFileError({ type: 'image/png', size: 1000 })).toBeNull()
    expect(avatarFileError({ type: 'image/jpeg', size: 1000 })).toBeNull()
    expect(avatarFileError({ type: 'image/webp', size: 1000 })).toBeNull()
    expect(avatarFileError({ type: 'image/gif', size: 1000 })).toBe('type')
    expect(avatarFileError({ type: 'image/svg+xml', size: 1000 })).toBe('type')
    expect(avatarFileError({ type: 'image/png', size: (AVATAR_MAX_FILE_MB + 1) * 1024 * 1024 })).toBe('size')
  })
})
