import { toValue, watchEffect, type MaybeRefOrGetter } from 'vue'

const APP_NAME = 'ArxMedia'

// Views set their own title and never reset it on unmount: the outgoing view
// can unmount after the incoming one has mounted (route <Transition>).
export function usePageTitle(title: MaybeRefOrGetter<string | null | undefined>): void {
  watchEffect(() => {
    const value = toValue(title)?.trim()
    document.title = value ? `${value} · ${APP_NAME}` : APP_NAME
  })
}
