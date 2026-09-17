interface NavigatorWithClientHints extends Navigator {
  readonly userAgentData?: { readonly mobile?: boolean }
}

/**
 * Whether the current device is a phone or tablet.
 *
 * The PWA install nudge is gated on this: desktop browsers keep their own
 * chrome install UI, we only prompt touch-first devices. Checked most
 * reliable signal first — a touchscreen laptop must still count as desktop.
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
