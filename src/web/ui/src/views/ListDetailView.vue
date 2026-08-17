<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div v-if="loading" class="space-y-4">
      <div class="h-8 skeleton rounded w-1/3"></div>
      <div class="h-4 skeleton rounded w-2/3"></div>
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mt-6">
        <div v-for="n in 10" :key="n" class="aspect-[2/3] skeleton rounded-lg"></div>
      </div>
    </div>

    <div v-else-if="list" class="space-y-6">
      <section class="card p-5 md:p-6">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="space-y-3 min-w-0">
            <div class="flex items-center gap-3 flex-wrap">
              <h1 class="font-display text-2xl text-primary font-semibold truncate">{{ list.name }}</h1>
              <span class="badge text-[10px]" :class="privacyClass(list.privacy)">{{ list.privacy }}</span>
            </div>
            <p class="text-sm text-secondary">{{ list.description || 'No description' }}</p>
            <p class="text-xs text-muted">
              {{ list.username }} · {{ list.item_count }} items · Created {{ formatDate(list.created_at) }}
            </p>
            <p class="text-xs text-muted">
              <span v-if="list.privacy === LIST_PRIVACY.PUBLIC">Public lists follow the owner profile visibility settings.</span>
              <span v-else>Private lists are visible only to owner and collaborators.</span>
            </p>
          </div>

          <div v-if="canEdit" class="flex gap-2 flex-wrap">
            <button @click="openEditModal" class="btn-ghost text-sm">Edit</button>
            <button @click="deleteList" class="btn-ghost text-sm border-red-500/40 text-red-300 hover:bg-red-500/10">Delete</button>
          </div>
        </div>

        <div class="mt-4 pt-4 border-t border-surface-200">
          <div class="flex items-center gap-3 flex-wrap text-xs">
            <p class="text-muted uppercase tracking-wide">Collaborators:</p>
            <div v-if="list.collaborator_users?.length" class="flex flex-wrap gap-2">
              <span
                v-for="user in list.collaborator_users"
                :key="`header-collab-${user.id}`"
                class="inline-flex items-center gap-2 rounded-full bg-brand-500/15 text-brand-300 px-2.5 py-1 text-xs"
              >
                <RouterLink :to="`/profile/${user.username}`" class="hover:text-primary transition-colors">{{ user.username }}</RouterLink>
              </span>
            </div>
            <p v-else class="text-muted">No collaborators yet.</p>
          </div>
        </div>
      </section>

      <section v-if="canEdit" class="card p-4 md:p-5 flex flex-wrap gap-2">
        <button @click="openAddModal" class="btn-primary text-sm inline-flex items-center whitespace-nowrap">
          <svg class="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
          Add Item
        </button>
        <button @click="openBulkModal" class="btn-ghost text-sm inline-flex items-center whitespace-nowrap">
          <svg class="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
          </svg>
          Bulk Add
        </button>
      </section>

      <section v-if="items.length" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <article v-for="item in items" :key="item.id" class="card group relative overflow-hidden">
          <RouterLink :to="item.media_type === MEDIA_TYPE.MOVIE ? `/movies/${item.tmdb_id}` : `/tv/${item.tmdb_id}`">
            <div class="aspect-[2/3] bg-surface-200 rounded-t-lg overflow-hidden">
              <img
                v-if="item.poster_url"
                :src="item.poster_url"
                :alt="item.title"
                class="w-full h-full object-cover group-hover:opacity-90 transition-opacity"
              />
              <div v-else class="w-full h-full flex items-center justify-center">
                <svg class="w-12 h-12 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 16h4m10 0h4M4 4h16v16H4z"/>
                </svg>
              </div>
            </div>
          </RouterLink>
          <div class="p-3">
            <RouterLink
              :to="item.media_type === MEDIA_TYPE.MOVIE ? `/movies/${item.tmdb_id}` : `/tv/${item.tmdb_id}`"
              class="text-sm text-primary truncate block hover:text-brand-400 transition-colors"
            >
              {{ item.title || 'Unknown' }}
            </RouterLink>
            <p class="text-xs text-muted mt-1">{{ item.year || '-' }} · {{ item.media_type }}</p>
          </div>
          <button
            v-if="canEdit"
            @click="removeItem(item.id)"
            class="absolute top-2 right-2 w-6 h-6 bg-red-500/80 hover:bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <svg class="w-3 h-3 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </article>
      </section>

      <section v-else class="card p-12 text-center">
        <p class="text-gray-500 text-lg mb-2">No items in this list yet</p>
        <p class="text-gray-600 text-sm mb-6">Add movies and shows to get started</p>
        <button v-if="canEdit" @click="openAddModal" class="btn-primary">Add Items</button>
      </section>

      <dialog
        ref="editDialog"
        closedby="any"
        class="list-dialog w-full max-w-xl rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
        aria-labelledby="edit-list-title"
        @close="onEditDialogClose"
        @click="onDialogClick($event, editDialog)"
      >
        <div class="p-6 md:p-7">
          <div class="flex items-start justify-between mb-5">
            <div>
              <h2 id="edit-list-title" class="text-xl font-display text-primary font-semibold">Edit List</h2>
              <p class="text-sm text-muted mt-1">Update list details and manage collaborators in one place.</p>
            </div>
            <button type="button" @click="closeEditModal" class="text-gray-500 hover:text-primary">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <form @submit.prevent="updateList" class="space-y-5">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Name</label>
              <input ref="editNameInput" v-model="editForm.name" type="text" required maxlength="200" class="input w-full">
              <p class="text-xs text-muted mt-1">{{ editForm.name.length }}/200</p>
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Description <span class="text-muted">(optional)</span></label>
              <textarea v-model="editForm.description" maxlength="1000" class="input w-full min-h-[96px]"></textarea>
              <p class="text-xs text-muted mt-1">{{ editForm.description.length }}/1000</p>
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-2">Privacy</label>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <button
                  type="button"
                  class="text-left rounded-lg border p-3 transition-colors"
                  :class="editForm.privacy === LIST_PRIVACY.PUBLIC ? 'border-brand-500 bg-brand-500/10' : 'border-surface-200 hover:border-surface-300'"
                  @click="editForm.privacy = LIST_PRIVACY.PUBLIC"
                >
                  <p class="text-sm font-medium text-primary">Public</p>
                  <p class="text-xs text-muted mt-1">Visibility follows your profile privacy settings.</p>
                </button>
                <button
                  type="button"
                  class="text-left rounded-lg border p-3 transition-colors"
                  :class="editForm.privacy === LIST_PRIVACY.PRIVATE ? 'border-brand-500 bg-brand-500/10' : 'border-surface-200 hover:border-surface-300'"
                  @click="editForm.privacy = LIST_PRIVACY.PRIVATE"
                >
                  <p class="text-sm font-medium text-primary">Private</p>
                  <p class="text-xs text-muted mt-1">Visible only to you and collaborators.</p>
                </button>
              </div>
            </div>

            <div v-if="isOwner" class="space-y-3">
              <label for="edit-collaborator-search" class="block text-sm text-gray-400 mb-1">Collaborators</label>
              <div class="relative">
                <input
                  id="edit-collaborator-search"
                  v-model="collaboratorQuery"
                  type="text"
                  autocomplete="off"
                  class="input w-full"
                  placeholder="Search username (min 3 chars)"
                  @input="searchCollaborators"
                >
                <div
                  v-if="showCollaboratorResults"
                  class="absolute z-20 mt-1 w-full rounded-lg border border-surface-200 bg-surface-100 shadow-xl max-h-56 overflow-y-auto"
                >
                  <button
                    v-for="user in collaboratorResults"
                    :key="`collab-result-${user.id}`"
                    type="button"
                    class="w-full text-left px-3 py-2 hover:bg-surface-200/70 transition-colors"
                    @click="addCollaborator(user)"
                  >
                    <p class="text-sm text-primary">{{ user.username }}</p>
                    <p v-if="user.bio" class="text-xs text-muted truncate">{{ user.bio }}</p>
                  </button>
                  <p v-if="!collaboratorResults.length && !searchingUsers" class="px-3 py-2 text-xs text-muted">No users found.</p>
                  <p v-if="searchingUsers" class="px-3 py-2 text-xs text-muted">Searching...</p>
                </div>
              </div>

              <div v-if="list.collaborator_users?.length" class="flex flex-wrap gap-2">
                <span
                  v-for="user in list.collaborator_users"
                  :key="`edit-collab-${user.id}`"
                  class="inline-flex items-center gap-2 rounded-full bg-brand-500/15 text-brand-300 px-2.5 py-1 text-xs"
                >
                  {{ user.username }}
                  <button type="button" class="text-brand-200 hover:text-primary" @click="removeCollaborator(user.id)">x</button>
                </span>
              </div>
              <div v-else class="rounded-md border border-surface-200 bg-surface-200/20 px-3 py-2 text-xs text-muted">
                No collaborators yet - add by username.
              </div>
            </div>

            <div class="flex gap-3 pt-1">
              <button type="button" @click="closeEditModal" class="btn-ghost flex-1">Cancel</button>
              <button type="submit" class="btn-primary flex-1" :disabled="updating">{{ updating ? 'Saving...' : 'Save Changes' }}</button>
            </div>
          </form>
        </div>
      </dialog>

      <dialog
        ref="addDialog"
        closedby="any"
        class="list-dialog w-full max-w-2xl rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
        aria-labelledby="add-list-item-title"
        @click="onDialogClick($event, addDialog)"
      >
        <div class="p-6 md:p-7">
          <h2 id="add-list-item-title" class="text-xl font-display text-primary font-semibold mb-4">Add to List</h2>
          <div class="mb-4">
            <input
              v-model="searchQuery"
              type="text"
              class="input w-full"
              placeholder="Search movies and shows..."
              @input="searchMedia"
            >
          </div>

          <div v-if="searching" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 mb-4">
            <div v-for="n in 8" :key="`search-skeleton-${n}`" class="aspect-[2/3] rounded-md skeleton"></div>
          </div>
          <div v-else-if="searchResults.length" class="max-h-[60vh] overflow-y-auto mb-4 pr-1">
            <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              <article
                v-for="result in searchResults"
                :key="`${result.media_type}-${result.tmdb_id}`"
                class="space-y-2"
              >
                <MediaCard
                  :item="result"
                  :media-type="result.media_type"
                  :watched="isWatchedStatus(result)"
                  :status="result.user_status?.status || 'none'"
                />
                <button type="button" class="btn-primary text-xs w-full" @click="addItem(result)">Add to List</button>
              </article>
            </div>
          </div>
          <p v-else-if="searchQuery && !searching" class="text-gray-500 text-sm text-center py-4">No results found</p>

          <div class="flex justify-end">
            <button type="button" @click="closeAddModal" class="btn-ghost">Close</button>
          </div>
        </div>
      </dialog>

      <dialog
        ref="bulkDialog"
        closedby="any"
        class="list-dialog w-full max-w-2xl rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
        aria-labelledby="bulk-add-title"
        @click="onDialogClick($event, bulkDialog)"
      >
        <div class="p-6 md:p-7">
          <h2 id="bulk-add-title" class="text-xl font-display text-primary font-semibold mb-4">Bulk Add Items</h2>
          <p class="text-gray-500 text-sm mb-4">
            Enter one item per line: <code class="text-xs text-gray-400">movie:550</code> or <code class="text-xs text-gray-400">tv:1399</code>
          </p>
          <textarea
            v-model="bulkItems"
            rows="8"
            class="input w-full font-mono text-sm"
            placeholder="movie:550&#10;tv:1399&#10;movie:680"
          ></textarea>
          <div class="flex gap-3 mt-4">
            <button type="button" @click="closeBulkModal" class="btn-ghost flex-1">Cancel</button>
            <button type="button" @click="bulkAdd" class="btn-primary flex-1" :disabled="bulkAdding">
              {{ bulkAdding ? 'Adding...' : 'Add Items' }}
            </button>
          </div>
        </div>
      </dialog>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authAPI, trackingAPI, mediaAPI } from '@/api'
import MediaCard from '@/components/MediaCard.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDateByLocale } from '@/i18n'
import { LIST_PRIVACY, MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const list = ref(null)
const items = ref([])
const loading = ref(true)
const updating = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)
const collaboratorQuery = ref('')
const collaboratorResults = ref([])
const showCollaboratorResults = ref(false)
const searchingUsers = ref(false)
const editDialog = ref(null)
const addDialog = ref(null)
const bulkDialog = ref(null)
const editNameInput = ref(null)
let collaboratorDebounce = null

const editForm = ref({
  name: '',
  description: '',
  privacy: LIST_PRIVACY.PUBLIC,
})

const isOwner = computed(() => {
  return auth.user?.username === list.value?.username
})

const canEdit = computed(() => {
  if (!list.value) return false
  if (isOwner.value) return true
  const myId = auth.user?.id
  if (!myId) return false
  return (list.value.collaborators || []).includes(myId)
})

function formatDate(d) {
  return formatDateByLocale(d)
}

function isWatchedStatus(item) {
  const status = item?.user_status?.status
  return status === WATCH_ENTRY_STATUS.WATCHED || status === WATCH_ENTRY_STATUS.WATCHING
}

function privacyClass(privacy) {
  const classes = {
    [LIST_PRIVACY.PUBLIC]: 'bg-green-500/20 text-green-400',
    [LIST_PRIVACY.PRIVATE]: 'bg-red-500/20 text-red-400',
  }
  return classes[privacy] || ''
}

function hasClosedBySupport() {
  return 'closedBy' in HTMLDialogElement.prototype
}

function onDialogClick(event, dialogRef) {
  if (hasClosedBySupport()) {
    return
  }
  const dialog = dialogRef?.value
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

function openEditModal() {
  editDialog.value?.showModal()
  nextTick(() => editNameInput.value?.focus())
}

function closeEditModal() {
  if (editDialog.value?.open) {
    editDialog.value.close()
  }
}

function onEditDialogClose() {
  if (list.value) {
    editForm.value = {
      name: list.value.name,
      description: list.value.description || '',
      privacy: list.value.privacy,
    }
  }
}

function openAddModal() {
  addDialog.value?.showModal()
}

function closeAddModal() {
  if (addDialog.value?.open) {
    addDialog.value.close()
  }
}

function openBulkModal() {
  bulkDialog.value?.showModal()
}

function closeBulkModal() {
  if (bulkDialog.value?.open) {
    bulkDialog.value.close()
  }
}

async function loadList() {
  loading.value = true
  try {
    const data = await trackingAPI.getList(route.params.id)
    if (data) {
      list.value = data
      editForm.value = {
        name: data.name,
        description: data.description || '',
        privacy: data.privacy
      }
      items.value = data.items || []
    }
  } catch (error) {
    console.error('Failed to load list:', error)
  } finally {
    loading.value = false
  }
}

async function updateList() {
  updating.value = true
  try {
    await trackingAPI.updateList(route.params.id, editForm.value)
    closeEditModal()
    await loadList()
  } catch (error) {
    console.error('Failed to update list:', error)
  } finally {
    updating.value = false
  }
}

async function deleteList() {
  if (!confirm('Are you sure you want to delete this list?')) return
  try {
    await trackingAPI.deleteList(route.params.id)
    router.push('/lists')
  } catch (error) {
    console.error('Failed to delete list:', error)
  }
}

async function searchMedia() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }
  searching.value = true
  try {
    const data = await mediaAPI.search(searchQuery.value, 'multi')
    if (data) {
      searchResults.value = (data.results || []).slice(0, 12).map((item) => ({
        ...item,
        media_type: item.media_type === MEDIA_TYPE.MOVIE ? MEDIA_TYPE.MOVIE : MEDIA_TYPE.TV,
        tmdb_id: item.tmdb_id || item.id,
      }))
    }
  } catch (error) {
    console.error('Search failed:', error)
  } finally {
    searching.value = false
  }
}

async function addItem(item) {
  try {
    await trackingAPI.addToList(route.params.id, {
      media_type: item.media_type,
      tmdb_id: item.tmdb_id
    })
    searchQuery.value = ''
    searchResults.value = []
    closeAddModal()
    await loadList()
  } catch (error) {
    console.error('Failed to add item:', error)
  }
}

async function removeItem(itemId) {
  if (!confirm('Remove this item from the list?')) return
  try {
    await trackingAPI.removeFromList(route.params.id, itemId)
    await loadList()
  } catch (error) {
    console.error('Failed to remove item:', error)
  }
}

async function addCollaborator(user) {
  if (!isOwner.value || !user?.id) return
  try {
    await trackingAPI.addCollaborator(route.params.id, Number(user.id))
    collaboratorQuery.value = ''
    collaboratorResults.value = []
    showCollaboratorResults.value = false
    await loadList()
  } catch (error) {
    console.error('Failed to add collaborator:', error)
  }
}

async function searchCollaborators() {
  const query = collaboratorQuery.value.trim()
  if (query.length < 3) {
    collaboratorResults.value = []
    showCollaboratorResults.value = false
    return
  }

  if (collaboratorDebounce) {
    clearTimeout(collaboratorDebounce)
  }

  collaboratorDebounce = setTimeout(async () => {
    searchingUsers.value = true
    showCollaboratorResults.value = true
    try {
      const data = await authAPI.searchUsers(query)
      const existingIds = new Set((list.value?.collaborator_users || []).map((entry) => entry.id))
      collaboratorResults.value = (data || []).filter((entry) => !existingIds.has(entry.id))
    } catch (error) {
      collaboratorResults.value = []
      console.error('Failed to search users:', error)
    } finally {
      searchingUsers.value = false
    }
  }, 250)
}

async function removeCollaborator(userId) {
  if (!isOwner.value) return
  try {
    await trackingAPI.removeCollaborator(route.params.id, userId)
    await loadList()
  } catch (error) {
    console.error('Failed to remove collaborator:', error)
  }
}

// Bulk add
const bulkItems = ref('')
const bulkAdding = ref(false)

async function bulkAdd() {
  if (!bulkItems.value.trim()) return
  
  bulkAdding.value = true
  try {
    const items = bulkItems.value.split('\n').map(line => {
      const [media_type, tmdb_id] = line.split(':')
      return { media_type: media_type.trim(), tmdb_id: parseInt(tmdb_id.trim()) }
    }).filter(item => item.media_type && item.tmdb_id)
    
    await trackingAPI.addToList(route.params.id, items)
    bulkItems.value = ''
    closeBulkModal()
    await loadList()
  } catch (error) {
    console.error('Failed to bulk add:', error)
  } finally {
    bulkAdding.value = false
  }
}

onMounted(() => {
  loadList()
})
</script>

<style scoped>
.list-dialog::backdrop {
  background: rgba(7, 8, 11, 0.72);
  backdrop-filter: blur(3px);
}

.list-dialog {
  margin: auto;
  inset: 0;
  max-height: calc(100vh - 2rem);
}
</style>
