import { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'

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
