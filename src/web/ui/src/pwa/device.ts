interface NavigatorWithClientHints extends Navigator {
  readonly userAgentData?: { readonly mobile?: boolean }
}

interface NavigatorWithStandalone extends Navigator {
  readonly standalone?: boolean
}

/**
 * Phone or tablet. Client hints first so touchscreen laptops count as desktop.
 */
export function isMobileDevice(): boolean {
  if (typeof navigator === 'undefined') return false

  const withHints = navigator as NavigatorWithClientHints
  if (typeof withHints.userAgentData?.mobile === 'boolean') return withHints.userAgentData.mobile

  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    try {
      if (window.matchMedia('(pointer: coarse)').matches) return true
    } catch {
      // matchMedia may throw outside real browsers; fall through to UA sniffing.
    }
  }

  const ua = navigator.userAgent
  if (/Android|iPhone|iPod|Mobile|Tablet/i.test(ua)) return true
  // iPadOS 13+ reports a desktop (Mac) UA; multi-touch gives it away.
  return /Mac/i.test(ua) && navigator.maxTouchPoints > 1
}

/** True when running inside the installed PWA rather than a browser tab. */
export function isInstalledApp(): boolean {
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    try {
      if (window.matchMedia('(display-mode: standalone)').matches) return true
    } catch {
      // matchMedia may throw outside real browsers; fall through.
    }
  }
  if (typeof navigator === 'undefined') return false
  // iOS Safari has no display-mode media query.
  return (navigator as NavigatorWithStandalone).standalone === true
}
