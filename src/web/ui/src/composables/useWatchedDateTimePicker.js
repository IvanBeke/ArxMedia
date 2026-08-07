import { ref } from 'vue'

export function useWatchedDateTimePicker() {
  const showDatePicker = ref(false)
  const pickerInitialValue = ref('')
  let pendingDatePickerResolve = null

  function pickWatchedDateTime(initialValue = '') {
    pickerInitialValue.value = initialValue
    showDatePicker.value = true
    return new Promise((resolve) => {
      pendingDatePickerResolve = resolve
    })
  }

  function handleDatePickerConfirm(isoValue) {
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
