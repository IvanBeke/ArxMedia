import { ref } from 'vue'

export function useUnwatchConfirm({ emit, perform }) {
  const confirmDialog = ref(null)
  const removing = ref(false)
  let target = null

  function open(confirmationTarget) {
    target = confirmationTarget
    confirmDialog.value?.showModal()
  }

  async function onConfirm() {
    if (removing.value || !target) return
    removing.value = true
    try {
      const done = await perform(target)
      if (!done) return
      confirmDialog.value?.close()
      emit('unwatched', target)
      target = null
    } finally {
      removing.value = false
    }
  }

  return { confirmDialog, removing, open, onConfirm }
}
