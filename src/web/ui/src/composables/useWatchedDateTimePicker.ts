import { ref } from 'vue'

export function useWatchedDateTimePicker() {
  const showDatePicker = ref(false)
  const pickerInitialValue = ref('')
  let pendingDatePickerResolve: ((value: string | null) => void) | null = null

  function pickWatchedDateTime(initialValue = ''): Promise<string | null> {
    pickerInitialValue.value = initialValue
    showDatePicker.value = true
    return new Promise((resolve) => {
      pendingDatePickerResolve = resolve
    })
  }

  function handleDatePickerConfirm(isoValue: string) {
    showDatePicker.value = false
    if (pendingDatePickerResolve) {
      pendingDatePickerResolve(isoValue)
      pendingDatePickerResolve = null
    }
  }

  function handleDatePickerCancel() {
    showDatePicker.value = false
    if (pendingDatePickerResolve) {
      pendingDatePickerResolve(null)
      pendingDatePickerResolve = null
    }
  }

  return {
    showDatePicker,
    pickerInitialValue,
    pickWatchedDateTime,
    handleDatePickerConfirm,
    handleDatePickerCancel,
  }
}
