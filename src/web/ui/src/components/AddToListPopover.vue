<template>
  <div class="relative" ref="rootRef">
    <button
      v-if="!modalMode"
      type="button"
      class="px-2 py-1 rounded-md text-xs border border-surface-200 text-muted hover:text-primary hover:bg-surface-200 transition-colors inline-flex items-center justify-center"
      :class="[iconOnly ? 'w-8 h-8 p-0' : '', buttonClass]"
      :disabled="loading"
      @click="toggleOpen"
      :title="iconOnly ? 'Add to list' : undefined"
      :aria-label="iconOnly ? 'Add to list' : undefined"
    >
      <svg v-if="iconOnly" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
      </svg>
      <span v-else>{{ loading ? '...' : 'Add to list' }}</span>
    </button>

    <div
      v-if="open"
      class="rounded-lg border border-surface-200 bg-surface-100 p-2"
      :class="modalMode ? 'w-full' : 'absolute right-0 mt-2 w-72 shadow-xl z-[120]'"
    >
      <p class="text-xs text-muted px-2 py-1">Add to existing list</p>
      <div class="max-h-40 overflow-y-auto">
        <button
          v-for="item in lists"
          :key="item.id"
          type="button"
          class="w-full text-left px-2 py-1.5 text-sm rounded-md hover:bg-surface-200 transition-colors"
          :disabled="submitting"
          @click="addToExisting(item.id)"
        >
          <span class="text-primary">{{ item.name }}</span>
          <span class="text-[11px] text-muted ml-1">({{ item.privacy }})</span>
        </button>
        <p v-if="!lists.length" class="px-2 py-2 text-xs text-muted">No lists yet</p>
      </div>

      <div class="mt-2 border-t border-surface-200 pt-2 px-1">
        <p class="text-xs text-muted mb-1">Create list and add</p>
        <div class="flex gap-1">
          <input
            v-model="newListName"
            type="text"
            class="input flex-1 min-w-0 text-sm py-1.5"
            placeholder="New list name"
            :disabled="submitting"
            @keydown.enter.prevent="createAndAdd"
          >
          <button
            type="button"
            class="btn-primary shrink-0 whitespace-nowrap text-xs px-2 py-1.5"
            :disabled="submitting || !newListName.trim()"
            @click="createAndAdd"
          >
            Create & add
          </button>
        </div>
      </div>

      <p v-if="successMsg" class="text-[11px] text-green-400 px-2 mt-2">{{ successMsg }}</p>
      <p v-if="errorMsg" class="text-[11px] text-red-400 px-2 mt-2">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { onMounted } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { trackingAPI } from '@/api'
import { LIST_PRIVACY } from '@/constants/tracking'
import { getApiErrorMessage } from '@/utils/errors'
import { useFlashMessages } from '@/composables/useFlashMessages'

const props = defineProps({
  mediaType: { type: String, required: true },
  tmdbId: { type: Number, required: true },
  iconOnly: { type: Boolean, default: false },
  buttonClass: { type: String, default: '' },
  startOpen: { type: Boolean, default: false },
  modalMode: { type: Boolean, default: false },
})

const open = ref(props.modalMode || props.startOpen)
const loading = ref(false)
const submitting = ref(false)
const lists = ref([])
const newListName = ref('')
const { successMsg, errorMsg, showSuccess: setSuccess, showError: setError } = useFlashMessages({ successDurationMs: 1800 })
const rootRef = ref(null)

const emit = defineEmits(['added'])

onClickOutside(rootRef, () => {
  if (props.modalMode) return
  open.value = false
})

onMounted(async () => {
  if (open.value) {
    await loadLists()
  }
})

async function loadLists() {
  loading.value = true
  try {
    const data = await trackingAPI.getLists()
    lists.value = data?.results || data || []
  } finally {
    loading.value = false
  }
}

async function toggleOpen() {
  if (props.modalMode) return
  open.value = !open.value
  if (open.value && !lists.value.length && !loading.value) {
    await loadLists()
  }
}

async function addToExisting(listId) {
  if (submitting.value) return
  submitting.value = true
  try {
    await trackingAPI.addToList(listId, { media_type: props.mediaType, tmdb_id: props.tmdbId })
    setSuccess('Added to list')
    emit('added')
  } catch (error) {
    setError(getApiErrorMessage(error, 'Could not add to list.'))
  } finally {
    submitting.value = false
  }
}

async function createAndAdd() {
  if (submitting.value) return
  const name = newListName.value.trim()
  if (!name) {
    setError('List name is required.')
    return
  }
  submitting.value = true
  try {
    const created = await trackingAPI.createList({ name, privacy: LIST_PRIVACY.PRIVATE })
    await trackingAPI.addToList(created.id, { media_type: props.mediaType, tmdb_id: props.tmdbId })
    newListName.value = ''
    await loadLists()
    setSuccess('List created and item added')
    emit('added')
  } catch (error) {
    setError(getApiErrorMessage(error, 'Could not create list and add item.'))
  } finally {
    submitting.value = false
  }
}

</script>
