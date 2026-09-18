import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Workbox } from 'workbox-window'
import { createWorkbox } from '@/pwa/client'
import { isInstalledApp, isMobileDevice } from '@/pwa/device'

export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const INSTALL_DISMISSED_KEY = 'pwa_install_dismissed'

function isInstallPrompt(event: Event): event is BeforeInstallPromptEvent {
  return 'prompt' in event && 'userChoice' in event
}

/** PWA install/update/offline UI state; safe where SW registration is unavailable. */
export function usePwa() {
  const needRefresh = ref(false)
  const offlineReady = ref(false)
  const installPrompt = ref<BeforeInstallPromptEvent | null>(null)
  const dismissed = ref(false)
  const isOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
  let workbox: Workbox | null = null

  try {
    dismissed.value = localStorage.getItem(INSTALL_DISMISSED_KEY) === 'true'
  } catch {
    dismissed.value = false
  }

  // Install prompts target phones/tablets, update prompts the installed app.
  // Evaluated once — neither device class nor launch mode changes at runtime.
  const isInstallTargetDevice = isMobileDevice()
  const canInstall = computed(
    () => installPrompt.value !== null && !dismissed.value && isInstallTargetDevice,
  )
  const installedApp = isInstalledApp()

  function onInstallPrompt(event: Event): void {
    if (!isInstallPrompt(event)) return
    event.preventDefault()
    installPrompt.value = event
  }

  function onNetworkChange(): void {
    isOnline.value = navigator.onLine
  }

  async function install(): Promise<void> {
    const prompt = installPrompt.value
    if (!prompt) return
    try {
      await prompt.prompt()
      await prompt.userChoice
    } catch {
      // prompt() rejects when the dialog cannot be shown; stay dismissible.
    } finally {
      installPrompt.value = null
    }
  }

  function dismissInstall(): void {
    dismissed.value = true
    installPrompt.value = null
    try {
      localStorage.setItem(INSTALL_DISMISSED_KEY, 'true')
    } catch {
      // Storage may be unavailable (private mode); dismissal just won't persist.
    }
  }

  function update(): void {
    void workbox?.messageSkipWaiting()
  }

  onMounted(() => {
    window.addEventListener('beforeinstallprompt', onInstallPrompt as EventListener)
    window.addEventListener('online', onNetworkChange)
    window.addEventListener('offline', onNetworkChange)

    workbox = createWorkbox()
    if (!workbox) return
    workbox.addEventListener('installed', (event) => {
      if (!event.isUpdate) offlineReady.value = true
    })
    workbox.addEventListener('waiting', () => {
      needRefresh.value = true
    })
    workbox.addEventListener('controlling', () => {
      window.location.reload()
    })
    void workbox.register().catch(() => {
      // Registration must never break app boot (e.g. worker 404 before first UI build).
    })
  })

  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', onInstallPrompt as EventListener)
    window.removeEventListener('online', onNetworkChange)
    window.removeEventListener('offline', onNetworkChange)
  })

  return { needRefresh, offlineReady, isOnline, canInstall, installedApp, install, dismissInstall, update }
}
