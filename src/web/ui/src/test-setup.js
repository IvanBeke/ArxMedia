import { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'

if (!globalThis.Temporal) {
  globalThis.Temporal = TemporalPolyfill
}

if (!Date.prototype.toTemporalInstant) {
  Date.prototype.toTemporalInstant = toTemporalInstant
}

if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute('open', '')
  }
}

if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.close) {
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute('open')
  }
}
