import { afterEach, describe, expect, it } from 'vitest'
import { isMobileDevice } from '@/pwa/device'

const DESKTOP_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
const IPHONE_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
const IPAD_DESKTOP_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15'

const originalUA = navigator.userAgent
const originalTouchPoints = navigator.maxTouchPoints

function setUA(ua: string): void {
  Object.defineProperty(navigator, 'userAgent', { configurable: true, value: ua })
}

function setTouchPoints(points: number): void {
  Object.defineProperty(navigator, 'maxTouchPoints', { configurable: true, value: points })
}

function setClientHintMobile(mobile: boolean): void {
  Object.defineProperty(navigator, 'userAgentData', { configurable: true, value: { mobile } })
}

function stubMatchMedia(matches: boolean): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: () => ({ matches }),
  })
}

afterEach(() => {
  setUA(originalUA)
  setTouchPoints(originalTouchPoints)
  delete (navigator as unknown as Record<string, unknown>).userAgentData
  delete (window as unknown as Record<string, unknown>).matchMedia
})

describe('isMobileDevice', () => {
  it('trusts client hints over touch capability (touchscreen laptop)', () => {
    setUA(DESKTOP_UA)
    setClientHintMobile(false)
    stubMatchMedia(true)

    expect(isMobileDevice()).toBe(false)
  })

  it('returns true from client hints on mobile', () => {
    setUA(IPHONE_UA)
    setClientHintMobile(true)

    expect(isMobileDevice()).toBe(true)
  })

  it('detects coarse pointers without client hints', () => {
    setUA(DESKTOP_UA)
    stubMatchMedia(true)

    expect(isMobileDevice()).toBe(true)
  })

  it('detects phones from the user agent', () => {
    setUA(IPHONE_UA)

    expect(isMobileDevice()).toBe(true)
  })

  it('treats desktop browsers as non-mobile', () => {
    setUA(DESKTOP_UA)

    expect(isMobileDevice()).toBe(false)
  })

  it('detects iPadOS reporting a desktop UA via touch points', () => {
    setUA(IPAD_DESKTOP_UA)
    setTouchPoints(5)

    expect(isMobileDevice()).toBe(true)
  })

  it('treats real Macs as non-mobile', () => {
    setUA(IPAD_DESKTOP_UA)
    setTouchPoints(0)

    expect(isMobileDevice()).toBe(false)
  })
})
