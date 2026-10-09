import { ref } from 'vue'
import { useCleanupOnUnmount } from '@/composables/useCleanupOnUnmount'

const DEFAULT_SUCCESS_DURATION_MS = 2500
const DEFAULT_ERROR_DURATION_MS = 3500

interface FlashMessageOptions { successDurationMs?: number; errorDurationMs?: number }

export function useFlashMessages({ successDurationMs = DEFAULT_SUCCESS_DURATION_MS, errorDurationMs = DEFAULT_ERROR_DURATION_MS }: FlashMessageOptions = {}) {
  const successMsg = ref('')
  const errorMsg = ref('')
  let successTimer: ReturnType<typeof setTimeout> | undefined
  let errorTimer: ReturnType<typeof setTimeout> | undefined

  useCleanupOnUnmount(() => {
    clearTimeout(successTimer)
    clearTimeout(errorTimer)
  })

  function showSuccess(msg: string) {
    errorMsg.value = ''
    clearTimeout(errorTimer)
    successMsg.value = msg
    clearTimeout(successTimer)
    successTimer = setTimeout(() => { successMsg.value = '' }, successDurationMs)
  }

  function showError(msg: string) {
    successMsg.value = ''
    clearTimeout(successTimer)
    errorMsg.value = msg
    clearTimeout(errorTimer)
    errorTimer = setTimeout(() => { errorMsg.value = '' }, errorDurationMs)
  }

  return { successMsg, errorMsg, showSuccess, showError }
}
