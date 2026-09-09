/// <reference types="vite/client" />

import type { Temporal as TemporalPolyfill, toTemporalInstant } from '@js-temporal/polyfill'

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare global {
  var Temporal: typeof TemporalPolyfill | undefined

  interface Date {
    toTemporalInstant?: typeof toTemporalInstant
  }
}

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guest?: boolean
  }
}

export {}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}
