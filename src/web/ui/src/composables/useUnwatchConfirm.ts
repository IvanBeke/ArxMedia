import { ref, type Ref } from 'vue'

export interface ConfirmDialogHandle { showModal: () => void; close: () => void }
interface UnwatchConfirmOptions<T> { emit: (event: 'unwatched', target: T) => void; perform: (target: T) => Promise<boolean> }

export function useUnwatchConfirm<T>({ emit, perform }: UnwatchConfirmOptions<T>): { confirmDialog: Ref<ConfirmDialogHandle | null>; removing: Ref<boolean>; open: (target: T) => void; onConfirm: () => Promise<void> } {
  const confirmDialog = ref<ConfirmDialogHandle | null>(null)
  const removing = ref(false)
  let target: T | null = null

  function open(confirmationTarget: T) {
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
