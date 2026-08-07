<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-8">
      <div>
        <h1 class="font-display text-2xl text-primary font-semibold">My Lists</h1>
        <p class="text-gray-500 text-sm mt-1">Create and manage your custom lists</p>
      </div>
      <button @click="showCreateModal = true" class="btn-primary">
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
      <button @click="showCreateModal = true" class="btn-primary">Create Your First List</button>
    </div>

    <!-- Create List Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content max-w-md">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-primary">Create New List</h2>
          <button @click="showCreateModal = false" class="text-gray-500 hover:text-primary">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <form @submit.prevent="createList">
          <div class="space-y-4">
            <div>
              <label class="block text-sm text-gray-400 mb-1">Name</label>
              <input v-model="newList.name" type="text" required class="input-field" placeholder="My Favorite Movies">
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Description</label>
              <textarea v-model="newList.description" class="input-field min-h-[80px]" placeholder="Describe your list..."></textarea>
            </div>
            <div>
              <label class="block text-sm text-gray-400 mb-1">Privacy</label>
              <select v-model="newList.privacy" class="input-field">
                <option :value="LIST_PRIVACY.PUBLIC">Public</option>
                <option :value="LIST_PRIVACY.FOLLOWERS">Followers Only</option>
                <option :value="LIST_PRIVACY.PRIVATE">Private</option>
              </select>
            </div>
          </div>
          <div class="flex gap-3 mt-6">
            <button type="button" @click="showCreateModal = false" class="btn-secondary flex-1">Cancel</button>
            <button type="submit" class="btn-primary flex-1" :disabled="creating">
              {{ creating ? 'Creating...' : 'Create List' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { trackingAPI } from '@/api'
import { LIST_PRIVACY } from '@/constants/tracking'

const lists = ref([])
const loading = ref(true)
const showCreateModal = ref(false)
const creating = ref(false)
const newList = ref({
  name: '',
  description: '',
  privacy: LIST_PRIVACY.PUBLIC,
})

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function privacyClass(privacy) {
  const classes = {
    [LIST_PRIVACY.PUBLIC]: 'bg-green-500/20 text-green-400',
    [LIST_PRIVACY.FOLLOWERS]: 'bg-yellow-500/20 text-yellow-400',
    [LIST_PRIVACY.PRIVATE]: 'bg-red-500/20 text-red-400',
  }
  return classes[privacy] || ''
}

async function createList() {
  creating.value = true
  try {
    await trackingAPI.createList(newList.value)
    newList.value = { name: '', description: '', privacy: LIST_PRIVACY.PUBLIC }
    showCreateModal.value = false
    await loadLists()
  } catch (error) {
    console.error('Failed to create list:', error)
  } finally {
    creating.value = false
  }
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
