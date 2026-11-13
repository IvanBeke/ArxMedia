import { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach } from 'vitest'

// Components and composables read the locale from the preferences store through
// useI18n(), so every test starts with an active Pinia; tests that need their own
// instance simply replace it.
beforeEach(() => {
  setActivePinia(createPinia())
})

// The polyfill's `Temporal` declarations are structurally distinct from the ambient
// ones TypeScript provides in `lib.esnext.temporal.d.ts`, though both describe the
// same TC-39 API, so the polyfill implementation is asserted to the global type here.
if (!globalThis.Temporal) {
  globalThis.Temporal = TemporalPolyfill as unknown as typeof Temporal
}

if (!Date.prototype.toTemporalInstant) {
  Date.prototype.toTemporalInstant = toTemporalInstant as Date['toTemporalInstant']
}

if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement): void {
    this.setAttribute('open', '')
  }
}

if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.close) {
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement): void {
    this.removeAttribute('open')
  }
}
