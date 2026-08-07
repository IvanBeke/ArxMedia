<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div v-if="loading" class="space-y-4">
      <div class="h-8 skeleton rounded w-1/3"></div>
      <div class="h-4 skeleton rounded w-2/3"></div>
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mt-6">
        <div v-for="n in 10" :key="n" class="aspect-[2/3] skeleton rounded-lg"></div>
      </div>
    </div>

    <div v-else-if="list">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6">
        <div class="flex-1">
          <div class="flex items-center gap-3 mb-2">
            <h1 class="font-display text-2xl text-primary font-semibold">{{ list.name }}</h1>
            <span class="badge text-[10px]" :class="privacyClass(list.privacy)">
              {{ list.privacy }}
            </span>
          </div>
          <p class="text-gray-500 text-sm">{{ list.description || 'No description' }}</p>
          <p class="text-gray-600 text-xs mt-2">
            {{ list.username }} • {{ list.item_count }} items • Created {{ formatDate(list.created_at) }}
          </p>
        </div>
      <div v-if="canEdit" class="flex gap-2">
        <button @click="showEditModal = true" class="btn-secondary text-sm">Edit</button>
        <button @click="deleteList" class="btn-danger text-sm">Delete</button>
      </div>
      </div>

      <!-- Add Item Buttons -->
      <div v-if="canEdit" class="mb-6 flex gap-2 flex-wrap">
        <button @click="showAddModal = true" class="btn-primary text-sm">
          <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
          Add Item
        </button>
        <button @click="showBulkModal = true" class="btn-secondary text-sm">
          <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/>
          </svg>
          Bulk Add
        </button>
        <div v-if="isOwner" class="flex items-center gap-2">
          <input v-model="collaboratorUserId" type="number" min="1" class="input text-sm w-32" placeholder="User ID" />
          <button @click="addCollaborator" class="btn-secondary text-sm">Add collaborator</button>
        </div>
      </div>

      <div v-if="list.collaborators?.length" class="mb-4 text-xs text-muted">
        Collaborators: {{ list.collaborators.join(', ') }}
      </div>

      <!-- Items Grid -->
      <div v-if="items.length" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <div v-for="item in items" :key="item.id" class="card group relative">
          <RouterLink :to="item.media_type === MEDIA_TYPE.MOVIE ? `/movies/${item.tmdb_id}` : `/tv/${item.tmdb_id}`">
            <div class="aspect-[2/3] bg-surface-200 rounded-t-lg overflow-hidden">
              <img
                v-if="item.poster_url"
                :src="item.poster_url"
                :alt="item.title"
                class="w-full h-full object-cover"
              />
              <div v-else class="w-full h-full flex items-center justify-center">
                <svg class="w-12 h-12 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 16h4m10 0h4M4 4h16v16H4z"/>
                </svg>
              </div>
            </div>
          </RouterLink>
          <div class="p-2">
            <RouterLink
              :to="item.media_type === MEDIA_TYPE.MOVIE ? `/movies/${item.tmdb_id}` : `/tv/${item.tmdb_id}`"
              class="text-sm text-primary truncate block hover:text-brand-400 transition-colors"
            >
              {{ item.title || 'Unknown' }}
            </RouterLink>
            <p class="text-xs text-gray-600">{{ item.year }}</p>
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
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="card p-12 text-center">
        <p class="text-gray-500 text-lg mb-2">No items in this list yet</p>
        <p class="text-gray-600 text-sm mb-6">Add movies and shows to get started</p>
        <button v-if="canEdit" @click="showAddModal = true" class="btn-primary">Add Items</button>
      </div>

      <!-- Edit Modal -->
      <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
        <div class="modal-content max-w-md">
          <h2 class="text-lg font-semibold text-primary mb-4">Edit List</h2>
          <form @submit.prevent="updateList">
            <div class="space-y-4">
              <div>
                <label class="block text-sm text-gray-400 mb-1">Name</label>
                <input v-model="editForm.name" type="text" required class="input-field">
              </div>
              <div>
                <label class="block text-sm text-gray-400 mb-1">Description</label>
                <textarea v-model="editForm.description" class="input-field min-h-[80px]"></textarea>
              </div>
              <div>
                <label class="block text-sm text-gray-400 mb-1">Privacy</label>
                <select v-model="editForm.privacy" class="input-field">
                  <option :value="LIST_PRIVACY.PUBLIC">Public</option>
                  <option :value="LIST_PRIVACY.FOLLOWERS">Followers Only</option>
                  <option :value="LIST_PRIVACY.PRIVATE">Private</option>
                </select>
              </div>
            </div>
            <div class="flex gap-3 mt-6">
              <button type="button" @click="showEditModal = false" class="btn-secondary flex-1">Cancel</button>
              <button type="submit" class="btn-primary flex-1" :disabled="updating">
                {{ updating ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Add Item Modal -->
      <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
        <div class="modal-content max-w-lg">
          <h2 class="text-lg font-semibold text-primary mb-4">Add to List</h2>
          <div class="mb-4">
            <input
              v-model="searchQuery"
              type="text"
              class="input-field"
              placeholder="Search movies and shows..."
              @input="searchMedia"
            />
          </div>
          <div v-if="searchResults.length" class="max-h-64 overflow-y-auto space-y-2 mb-4">
            <div
              v-for="result in searchResults"
              :key="`${result.media_type}-${result.tmdb_id}`"
              class="flex items-center gap-3 p-2 rounded hover:bg-surface-200 cursor-pointer transition-colors"
              @click="addItem(result)"
            >
              <img
                v-if="result.poster_path"
                :src="`https://image.tmdb.org/t/p/w92${result.poster_path}`"
                :alt="result.title"
                class="w-10 h-14 object-cover rounded"
              />
              <div class="flex-1 min-w-0">
                <p class="text-sm text-primary truncate">{{ result.title }}</p>
                <p class="text-xs text-gray-500">{{ result.year }} • {{ result.media_type }}</p>
              </div>
            </div>
          </div>
          <p v-else-if="searchQuery && !searching" class="text-gray-500 text-sm text-center py-4">
            No results found
          </p>
<div class="flex justify-end">
            <button @click="showAddModal = false" class="btn-secondary">Close</button>
          </div>
        </div>
      </div>

      <!-- Bulk Add Modal -->
      <div v-if="showBulkModal" class="modal-overlay" @click.self="showBulkModal = false">
        <div class="modal-content max-w-lg">
          <h2 class="text-lg font-semibold text-primary mb-4">Bulk Add Items</h2>
          <p class="text-gray-500 text-sm mb-4">
            Enter items in format: media_type:tmdb_id (one per line). Example:<br/>
            <code class="text-xs text-gray-400">movie:550<br/>tv:1399</code>
          </p>
          <textarea
            v-model="bulkItems"
            rows="8"
            class="input-field font-mono text-sm"
            placeholder="movie:550&#10;tv:1399&#10;movie:680"
          ></textarea>
          <div class="flex gap-3 mt-4">
            <button type="button" @click="showBulkModal = false" class="btn-secondary flex-1">Cancel</button>
            <button @click="bulkAdd" class="btn-primary flex-1" :disabled="bulkAdding">
              {{ bulkAdding ? 'Adding...' : 'Add Items' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { trackingAPI, mediaAPI } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { formatDateByLocale } from '@/i18n'
import { LIST_PRIVACY, MEDIA_TYPE } from '@/constants/tracking'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const list = ref(null)
const items = ref([])
const loading = ref(true)
const showEditModal = ref(false)
const showAddModal = ref(false)
const updating = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)
const collaboratorUserId = ref('')

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

function privacyClass(privacy) {
  const classes = {
    [LIST_PRIVACY.PUBLIC]: 'bg-green-500/20 text-green-400',
    [LIST_PRIVACY.FOLLOWERS]: 'bg-yellow-500/20 text-yellow-400',
    [LIST_PRIVACY.PRIVATE]: 'bg-red-500/20 text-red-400',
  }
  return classes[privacy] || ''
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
    showEditModal.value = false
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
      searchResults.value = (data.results || []).slice(0, 10).map(item => ({
        media_type: item.media_type === MEDIA_TYPE.MOVIE ? MEDIA_TYPE.MOVIE : MEDIA_TYPE.TV,
        tmdb_id: item.tmdb_id || item.id,
        title: item.title || item.name,
        poster_path: item.poster_path,
        year: item.release_date ? item.release_date.substring(0, 4) : item.first_air_date ? item.first_air_date.substring(0, 4) : ''
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
    showAddModal.value = false
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

async function addCollaborator() {
  if (!isOwner.value || !collaboratorUserId.value) return
  try {
    await trackingAPI.addCollaborator(route.params.id, Number(collaboratorUserId.value))
    collaboratorUserId.value = ''
    await loadList()
  } catch (error) {
    console.error('Failed to add collaborator:', error)
  }
}

// Bulk add
const showBulkModal = ref(false)
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
    showBulkModal.value = false
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
