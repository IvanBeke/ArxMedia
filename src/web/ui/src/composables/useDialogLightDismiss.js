export function supportsDialogClosedBy() {
  return typeof HTMLDialogElement !== 'undefined' && 'closedBy' in HTMLDialogElement.prototype
}

export function closeOnDialogBackdropClick(event, dialog, onClose = null) {
  if (supportsDialogClosedBy()) {
    return false
  }
  if (!dialog || event.target !== dialog) {
    return false
  }

  const rect = dialog.getBoundingClientRect()
  const clickedInside = (
    rect.top <= event.clientY
    && event.clientY <= rect.top + rect.height
    && rect.left <= event.clientX
    && event.clientX <= rect.left + rect.width
  )
  if (clickedInside) {
    return false
  }

  if (typeof onClose === 'function') {
    onClose()
  } else {
    dialog.close()
  }
  return true
}
