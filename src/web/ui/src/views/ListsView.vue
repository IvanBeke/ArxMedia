<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">My Lists</h1>
        <p class="text-gray-500 text-sm mt-1">Create and manage your custom lists</p>
      </div>
      <button @click="openCreateModal" class="btn-primary inline-flex items-center whitespace-nowrap">
        <svg class="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        Create List
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="n in 6" :key="n" class="h-32 skeleton rounded-lg"></div>
    </div>

    <!-- Lists Grid -->
    <div v-else-if="lists.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <RouterLink
        v-for="list in lists"
        :key="list.id"
        :to="`/lists/${list.id}`"
        class="card p-4 hover:bg-surface-200/50 transition-colors"
      >
        <div class="flex items-start justify-between mb-2">
          <h3 class="text-primary font-medium truncate flex-1">{{ list.name }}</h3>
          <span class="badge ml-2 text-[10px]" :class="privacyClass(list.privacy)">
            {{ list.privacy }}
          </span>
        </div>
        <p class="text-gray-500 text-sm mb-3 line-clamp-2">{{ list.description || 'No description' }}</p>
        <div class="flex items-center justify-between text-xs text-gray-600">
          <span>{{ list.item_count }} items</span>
          <span>{{ formatDate(list.created_at) }}</span>
        </div>
      </RouterLink>
    </div>

    <!-- Empty State -->
    <div v-else class="card p-12 text-center">
      <svg class="w-16 h-16 text-gray-700 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
      </svg>
      <p class="text-gray-500 text-lg mb-2">No lists yet</p>
      <p class="text-gray-600 text-sm mb-6">Create your first custom list to organize your movies and shows</p>
      <button @click="openCreateModal" class="btn-primary">Create Your First List</button>
    </div>

    <dialog
      ref="createDialog"
      closedby="any"
      class="create-list-dialog w-full max-w-2xl rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
      aria-labelledby="create-list-title"
      @close="onDialogClose"
      @click="onDialogClick"
    >
      <div class="p-6 md:p-7">
        <div class="flex items-start justify-between mb-5">
          <div>
            <h2 id="create-list-title" class="text-xl font-display text-primary font-semibold">Create New List</h2>
            <p class="text-sm text-muted mt-1">Name your list, add context, set privacy, and invite collaborators.</p>
          </div>
          <button type="button" @click="closeCreateModal" class="text-gray-500 hover:text-primary">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <form @submit.prevent="createList" class="space-y-5">
          <div>
            <label for="list-name" class="block text-sm text-gray-400 mb-1">List Name</label>
            <input
              id="list-name"
              ref="nameInput"
              v-model="newList.name"
              type="text"
              required
              maxlength="200"
              class="input w-full"
              placeholder="My Weekend Watch Picks"
            >
            <p class="text-xs text-muted mt-1">{{ newList.name.length }}/200</p>
          </div>

          <div>
            <label for="list-description" class="block text-sm text-gray-400 mb-1">Description <span class="text-muted">(optional)</span></label>
            <textarea
              id="list-description"
              v-model="newList.description"
              class="input w-full min-h-[96px]"
              maxlength="1000"
              placeholder="A quick note about what this list tracks and why."
            ></textarea>
            <p class="text-xs text-muted mt-1">{{ newList.description.length }}/1000</p>
          </div>

          <div>
            <label class="block text-sm text-gray-400 mb-2">Privacy</label>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                type="button"
                class="text-left rounded-lg border p-3 transition-colors"
                :class="newList.privacy === LIST_PRIVACY.PUBLIC ? 'border-brand-500 bg-brand-500/10' : 'border-surface-200 hover:border-surface-300'"
                @click="newList.privacy = LIST_PRIVACY.PUBLIC"
              >
                <p class="text-sm font-medium text-primary">Public</p>
                <p class="text-xs text-muted mt-1">Visibility follows your profile privacy settings.</p>
              </button>
              <button
                type="button"
                class="text-left rounded-lg border p-3 transition-colors"
                :class="newList.privacy === LIST_PRIVACY.PRIVATE ? 'border-brand-500 bg-brand-500/10' : 'border-surface-200 hover:border-surface-300'"
                @click="newList.privacy = LIST_PRIVACY.PRIVATE"
              >
                <p class="text-sm font-medium text-primary">Private</p>
                <p class="text-xs text-muted mt-1">Visible only to you and collaborators.</p>
              </button>
            </div>
          </div>

          <div>
            <label for="collaborator-search" class="block text-sm text-gray-400 mb-1">Collaborators <span class="text-muted">(optional)</span></label>
            <div class="relative">
              <input
                id="collaborator-search"
                v-model="collaboratorQuery"
                type="text"
                autocomplete="off"
                class="input w-full"
                placeholder="Search username (min 3 chars)"
                @input="searchCollaborators"
              >
              <div
                v-if="showUserResults"
                class="absolute z-20 mt-1 w-full rounded-lg border border-surface-200 bg-surface-100 shadow-xl max-h-56 overflow-y-auto"
              >
                <button
                  v-for="user in collaboratorResults"
                  :key="`user-result-${user.id}`"
                  type="button"
                  class="w-full text-left px-3 py-2 hover:bg-surface-200/70 transition-colors"
                  @click="selectCollaborator(user)"
                >
                  <p class="text-sm text-primary">{{ user.username }}</p>
                  <p v-if="user.bio" class="text-xs text-muted truncate">{{ user.bio }}</p>
                </button>
                <p v-if="!collaboratorResults.length && !searchingUsers" class="px-3 py-2 text-xs text-muted">No users found.</p>
                <p v-if="searchingUsers" class="px-3 py-2 text-xs text-muted">Searching...</p>
              </div>
            </div>

            <div v-if="selectedCollaborators.length" class="mt-3 flex flex-wrap gap-2">
              <span
                v-for="user in selectedCollaborators"
                :key="`selected-collab-${user.id}`"
                class="inline-flex items-center gap-2 rounded-full bg-brand-500/15 text-brand-300 px-2.5 py-1 text-xs"
              >
                {{ user.username }}
                <button type="button" class="text-brand-200 hover:text-primary" @click="removeCollaborator(user.id)">x</button>
              </span>
            </div>
            <p class="text-xs text-muted mt-2">Collaborators can view private lists and add items.</p>
          </div>

          <div v-if="createError" class="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {{ createError }}
          </div>

          <div class="flex gap-3 pt-1">
            <button type="button" @click="closeCreateModal" class="btn-secondary flex-1">Cancel</button>
            <button type="submit" class="btn-primary flex-1" :disabled="creating || !newList.name.trim()">
              {{ creating ? 'Creating...' : 'Create List' }}
            </button>
          </div>
        </form>
      </div>
    </dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { authAPI, trackingAPI } from '@/api'
import { LIST_PRIVACY } from '@/constants/tracking'

const lists = ref([])
const loading = ref(true)
const creating = ref(false)
const createError = ref('')
const createDialog = ref(null)
const nameInput = ref(null)
const collaboratorQuery = ref('')
const collaboratorResults = ref([])
const selectedCollaborators = ref([])
const searchingUsers = ref(false)
let searchDebounce = null
const newList = ref({
  name: '',
  description: '',
  privacy: LIST_PRIVACY.PUBLIC,
})

const showUserResults = ref(false)

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function privacyClass(privacy) {
  const classes = {
    [LIST_PRIVACY.PUBLIC]: 'bg-green-500/20 text-green-400',
    [LIST_PRIVACY.PRIVATE]: 'bg-red-500/20 text-red-400',
  }
  return classes[privacy] || ''
}

async function createList() {
  createError.value = ''
  creating.value = true
  try {
    const created = await trackingAPI.createList(newList.value)

    if (selectedCollaborators.value.length && created?.id) {
      const collaboratorCalls = selectedCollaborators.value.map((user) =>
        trackingAPI.addCollaborator(created.id, user.id)
      )
      const results = await Promise.allSettled(collaboratorCalls)
      const failedCount = results.filter((r) => r.status === 'rejected').length
      if (failedCount > 0) {
        console.warn(`List created, but ${failedCount} collaborator${failedCount > 1 ? 's were' : ' was'} not added.`)
      }
    }

    closeCreateModal()
    resetCreateForm()
    await loadLists()
  } catch (error) {
    createError.value = error?.detail || 'Failed to create list.'
    console.error('Failed to create list:', error)
  } finally {
    creating.value = false
  }
}

function resetCreateForm() {
  newList.value = { name: '', description: '', privacy: LIST_PRIVACY.PUBLIC }
  collaboratorQuery.value = ''
  collaboratorResults.value = []
  selectedCollaborators.value = []
  showUserResults.value = false
  createError.value = ''
}

function openCreateModal() {
  createDialog.value?.showModal()
  nextTick(() => nameInput.value?.focus())
}

function closeCreateModal() {
  if (createDialog.value?.open) {
    createDialog.value.close()
  }
}

function onDialogClose() {
  collaboratorResults.value = []
  showUserResults.value = false
}

function onDialogClick(event) {
  if ('closedBy' in HTMLDialogElement.prototype) {
    return
  }
  const dialog = createDialog.value
  if (!dialog || event.target !== dialog) {
    return
  }

  const rect = dialog.getBoundingClientRect()
  const clickedInside = (
    rect.top <= event.clientY
    && event.clientY <= rect.top + rect.height
    && rect.left <= event.clientX
    && event.clientX <= rect.left + rect.width
  )
  if (!clickedInside) {
    dialog.close()
  }
}

function selectCollaborator(user) {
  if (selectedCollaborators.value.some((row) => row.id === user.id)) {
    collaboratorQuery.value = ''
    collaboratorResults.value = []
    showUserResults.value = false
    return
  }
  selectedCollaborators.value.push(user)
  collaboratorQuery.value = ''
  collaboratorResults.value = []
  showUserResults.value = false
}

function removeCollaborator(userId) {
  selectedCollaborators.value = selectedCollaborators.value.filter((user) => user.id !== userId)
}

async function searchCollaborators() {
  const query = collaboratorQuery.value.trim()
  if (query.length < 3) {
    collaboratorResults.value = []
    showUserResults.value = false
    return
  }

  if (searchDebounce) {
    clearTimeout(searchDebounce)
  }

  searchDebounce = setTimeout(async () => {
    searchingUsers.value = true
    showUserResults.value = true
    try {
      const data = await authAPI.searchUsers(query)
      const selectedIds = new Set(selectedCollaborators.value.map((user) => user.id))
      collaboratorResults.value = (data || []).filter((user) => !selectedIds.has(user.id))
    } catch (error) {
      collaboratorResults.value = []
      console.error('Failed to search users:', error)
    } finally {
      searchingUsers.value = false
    }
  }, 250)
}

async function loadLists() {
  loading.value = true
  try {
    const data = await trackingAPI.getLists()
    if (data) {
      lists.value = data.results || data
    }
  } catch (error) {
    console.error('Failed to load lists:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadLists()
})
</script>

<style scoped>
.create-list-dialog::backdrop {
  background: rgba(7, 8, 11, 0.72);
  backdrop-filter: blur(3px);
}

.create-list-dialog {
  margin: auto;
  inset: 0;
  max-height: calc(100vh - 2rem);
}
</style>
