<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <WatchedDateTimePicker
      :open="showDatePicker"
      :initial-value="pickerInitialValue"
      title="When did you watch this?"
      @confirm="handleDatePickerConfirm"
      @cancel="handleDatePickerCancel"
    />

    <Transition name="fade">
      <div v-if="quickActionError" class="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
        {{ quickActionError }}
      </div>
    </Transition>

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
            <button @click="openAddModal" class="btn-ghost text-sm inline-flex items-center whitespace-nowrap border-brand-500/40 text-brand-300 hover:bg-brand-500/10">
              <svg class="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
              </svg>
              Add Item
            </button>
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

      <MediaFilterBar
        :show-media-type-filter="true"
        :show-status-filter="false"
        :show-provider-status-filter="false"
        :show-genre-filter="true"
        :show-quick-filter-has-upcoming="false"
        :show-quick-filter-new-only="false"
        :show-quick-filter-missing-rating="false"
        :show-search="true"
        :show-sort="true"
        :show-direction="true"
        search-placeholder="Search list items by title"
        :sync-url="true"
        @change="onFilterBarChange"
      />

      <Transition name="fade">
        <div v-if="feedbackMsg" class="px-3 py-2 rounded-md text-sm" :class="feedbackKind === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-green-500/10 border border-green-500/20 text-green-400'">
          {{ feedbackMsg }}
        </div>
      </Transition>

      <section v-if="items.length" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <article v-for="item in items" :key="item.id" class="group relative">
          <MediaCard
            :item="item"
            :media-type="item.media_type"
            :watched="isWatchedStatus(item)"
            :status="item.user_status?.status || 'none'"
            :show-quick-action="canToggleWatchlist(item)"
            :quick-action-active="item.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH"
            :quick-action-loading="isLoading(item.media_type, item.tmdb_id)"
            :quick-action-pulsing="isPulsing(item.media_type, item.tmdb_id)"
            :quick-action-aria-label="getWatchlistAriaLabel(item.media_type, item.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH)"
            :show-watched-quick-action="true"
            :watched-quick-action-loading="isWatchedLoading(item.media_type, item.tmdb_id)"
            :watched-quick-action-pulsing="isWatchedPulsing(item.media_type, item.tmdb_id)"
            watched-quick-action-aria-label="Mark as watched"
            remove-watched-quick-action-aria-label="Remove from watched history"
            :remove-watched-quick-action-confirm-text="getRemoveHistoryConfirmText(item.media_type)"
            @quick-action-watchlist="handleQuickAction(item, item.media_type)"
            @quick-action-watch-option="handleWatchOption(item, item.media_type, $event)"
            @quick-action-remove-watched="handleRemoveWatched(item, item.media_type)"
          />
          <div v-if="canEdit" class="absolute top-2 right-2 z-20 list-item-menu" :class="{ 'is-open': openItemMenuId === item.id }">
            <button
              type="button"
              class="list-item-menu-trigger"
              aria-label="List item actions"
              title="List item actions"
              @click.stop="toggleItemMenu(item.id)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h.01M12 12h.01M19 12h.01"/>
              </svg>
            </button>
            <div v-if="openItemMenuId === item.id" class="list-item-menu-panel">
              <button
                type="button"
                class="list-item-menu-danger"
                @click="openRemoveDialog(item, $event)"
              >
                Remove from list
              </button>
            </div>
          </div>
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
        ref="removeDialog"
        closedby="any"
        class="list-dialog w-full max-w-md rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
        aria-labelledby="remove-item-title"
        @close="onRemoveDialogClose"
        @click="onDialogClick($event, removeDialog)"
      >
        <div class="p-6">
          <h2 id="remove-item-title" class="text-lg font-display text-primary font-semibold">Remove from this list?</h2>
          <p class="mt-2 text-sm text-muted">This removes the item from this list only. It does not remove watch history or ratings.</p>
          <div class="mt-5 flex gap-3">
            <button type="button" class="btn-ghost flex-1" @click="closeRemoveDialog">Keep item</button>
            <button type="button" class="btn-ghost flex-1 border-red-500/40 text-red-300 hover:bg-red-500/10" :disabled="removingItem" @click="confirmRemoveItem">
              {{ removingItem ? 'Removing...' : 'Remove' }}
            </button>
          </div>
        </div>
      </dialog>

    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authAPI, trackingAPI, mediaAPI } from '@/api'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import MediaCard from '@/components/MediaCard.vue'
import WatchedDateTimePicker from '@/components/WatchedDateTimePicker.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDateByLocale } from '@/i18n'
import { LIST_PRIVACY, MEDIA_TYPE, WATCH_ENTRY_STATUS } from '@/constants/tracking'
import { getApiErrorMessage } from '@/utils/errors'
import { useWatchlistQuickActions } from '@/composables/useWatchlistQuickActions'
import { useWatchedQuickActions } from '@/composables/useWatchedQuickActions'
import { useWatchedDateTimePicker } from '@/composables/useWatchedDateTimePicker'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const list = ref(null)
const items = ref([])
const loading = ref(true)
const updating = ref(false)
const loadingItems = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)
const collaboratorQuery = ref('')
const collaboratorResults = ref([])
const showCollaboratorResults = ref(false)
const searchingUsers = ref(false)
const editDialog = ref(null)
const addDialog = ref(null)
const removeDialog = ref(null)
const editNameInput = ref(null)
let collaboratorDebounce = null
const appliedFilters = ref({
  search: '',
  sort: 'added_at',
  direction: 'desc',
  mediaType: 'all',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
})
const feedbackMsg = ref('')
const feedbackKind = ref('success')
const quickActionError = ref('')
const pendingRemovalItem = ref(null)
const removingItem = ref(false)
const openItemMenuId = ref(null)

const editForm = ref({
  name: '',
  description: '',
  privacy: LIST_PRIVACY.PUBLIC,
})

const { showDatePicker, pickerInitialValue, pickWatchedDateTime, handleDatePickerConfirm, handleDatePickerCancel } = useWatchedDateTimePicker()
const { isLoading, isPulsing, toggleWatchlist } = useWatchlistQuickActions()
const { isLoading: isWatchedLoading, isPulsing: isWatchedPulsing, markWatched, unmarkWatched } = useWatchedQuickActions()

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

function showFeedback(message, kind = 'success') {
  feedbackKind.value = kind
  feedbackMsg.value = message
  setTimeout(() => {
    if (feedbackMsg.value === message) {
      feedbackMsg.value = ''
    }
  }, 3500)
}

function isWatchedStatus(item) {
  const status = item?.user_status?.status
  return status === WATCH_ENTRY_STATUS.WATCHED || status === WATCH_ENTRY_STATUS.WATCHING
}

function canToggleWatchlist(item) {
  const status = item?.user_status?.status
  return status !== WATCH_ENTRY_STATUS.WATCHED && status !== WATCH_ENTRY_STATUS.WATCHING
}

function getWatchlistAriaLabel(mediaType, inWatchlist) {
  if (mediaType === MEDIA_TYPE.TV) {
    return inWatchlist ? 'Remove show from watchlist' : 'Add show to watchlist'
  }
  return inWatchlist ? 'Remove movie from watchlist' : 'Add movie to watchlist'
}

function getRemoveHistoryConfirmText(mediaType) {
  if (mediaType === MEDIA_TYPE.TV) {
    return 'Remove show from watched history?'
  }
  return 'Remove movie from watched history?'
}

function showQuickActionError(message) {
  quickActionError.value = message
  setTimeout(() => {
    quickActionError.value = ''
  }, 3500)
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

function toggleItemMenu(itemId) {
  openItemMenuId.value = openItemMenuId.value === itemId ? null : itemId
}

function closeItemMenu() {
  openItemMenuId.value = null
}

function openRemoveDialog(item, event) {
  if (event) {
    event.stopPropagation()
  }
  closeItemMenu()
  pendingRemovalItem.value = item
  removeDialog.value?.showModal()
}

function closeRemoveDialog() {
  if (removeDialog.value?.open) {
    removeDialog.value.close()
  }
}

function onRemoveDialogClose() {
  pendingRemovalItem.value = null
  removingItem.value = false
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
    showFeedback(getApiErrorMessage(error, 'Could not load list.'), 'error')
  } finally {
    loading.value = false
  }
}

async function loadItems() {
  loadingItems.value = true
  try {
    const filterState = appliedFilters.value
    const params = {
      sort: filterState.sort,
      direction: filterState.direction,
      ...(filterState.search ? { search: filterState.search } : {}),
      ...(filterState.mediaType !== 'all' ? { media_type: filterState.mediaType } : {}),
      ...(filterState.genres.length ? { genres: filterState.genres } : {}),
    }
    const data = await trackingAPI.getListItems(route.params.id, params)
    items.value = data?.results || data || []
  } catch (error) {
    showFeedback(getApiErrorMessage(error, 'Could not load list items.'), 'error')
    items.value = []
  } finally {
    loadingItems.value = false
  }
}

function onFilterBarChange(payload) {
  const next = payload?.filters
  if (!next) return
  appliedFilters.value = next
}

async function updateList() {
  updating.value = true
  try {
    await trackingAPI.updateList(route.params.id, editForm.value)
    closeEditModal()
    await loadList()
  } catch (error) {
    console.error('Failed to update list:', error)
    showFeedback(getApiErrorMessage(error, 'Could not update list.'), 'error')
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
    showFeedback(getApiErrorMessage(error, 'Could not delete list.'), 'error')
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
    await loadItems()
    showFeedback('Item added to list.')
  } catch (error) {
    showFeedback(getApiErrorMessage(error, 'Could not add item to list.'), 'error')
  }
}

async function removeItem(itemId) {
  try {
    await trackingAPI.removeFromList(route.params.id, itemId)
    await loadItems()
    showFeedback('Item removed from list.')
  } catch (error) {
    showFeedback(getApiErrorMessage(error, 'Could not remove item from list.'), 'error')
  }
}

async function confirmRemoveItem() {
  const itemId = pendingRemovalItem.value?.id
  if (!itemId || removingItem.value) {
    return
  }
  removingItem.value = true
  try {
    await removeItem(itemId)
    closeRemoveDialog()
  } finally {
    removingItem.value = false
  }
}

async function handleQuickAction(item, mediaType) {
  try {
    if (!canToggleWatchlist(item)) {
      return
    }

    const inWatchlist = item?.user_status?.status === WATCH_ENTRY_STATUS.PLAN_TO_WATCH
    const result = await toggleWatchlist(mediaType, item.tmdb_id, inWatchlist)
    item.user_status = {
      ...(item.user_status || {}),
      status: result === 'removed' ? WATCH_ENTRY_STATUS.NONE : WATCH_ENTRY_STATUS.PLAN_TO_WATCH,
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watchlist.'))
  }
}

async function handleWatchOption(item, mediaType, option) {
  try {
    let watchedAt = null
    if (option === 'release') {
      const releaseDate = item.release_date || item.first_air_date
      watchedAt = releaseDate ? `${releaseDate}T00:00:00Z` : null
    } else if (option === 'date') {
      watchedAt = await pickWatchedDateTime(item?.user_status?.watched_at || '')
      if (!watchedAt) {
        return
      }
    }

    const nextStatus = await markWatched(mediaType, item.tmdb_id, watchedAt)
    if (!nextStatus) {
      return
    }

    const nowIso = watchedAt || new Date().toISOString()
    item.user_status = {
      ...(item.user_status || {}),
      status: nextStatus,
      watched_at: nowIso,
      status_changed_at: nowIso,
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watched status.'))
  }
}

async function handleRemoveWatched(item, mediaType) {
  try {
    const removed = await unmarkWatched(mediaType, item.tmdb_id)
    if (!removed) {
      return
    }

    item.user_status = {
      ...(item.user_status || {}),
      status: WATCH_ENTRY_STATUS.NONE,
      watched_at: null,
      status_changed_at: null,
    }
  } catch (error) {
    showQuickActionError(getApiErrorMessage(error, 'Could not update watched status.'))
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
    showFeedback(getApiErrorMessage(error, 'Could not add collaborator.'), 'error')
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
    showFeedback(getApiErrorMessage(error, 'Could not remove collaborator.'), 'error')
  }
}

onMounted(async () => {
  document.addEventListener('click', handleDocumentClick)
  await loadList()
  await loadItems()
})

function handleDocumentClick(event) {
  if (!openItemMenuId.value) return
  const target = event.target
  if (!(target instanceof Element)) {
    closeItemMenu()
    return
  }
  if (!target.closest('.list-item-menu')) {
    closeItemMenu()
  }
}

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})

watch(
  appliedFilters,
  async () => {
    await loadItems()
  },
  { deep: true }
)
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

.list-item-menu {
  opacity: 0;
  transition: opacity 0.2s;
}

.group:hover .list-item-menu,
.list-item-menu.is-open {
  opacity: 1;
}

.list-item-menu-trigger {
  list-style: none;
  width: 1.75rem;
  height: 1.75rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  border: 1px solid var(--bg-surface-200);
  background: color-mix(in srgb, var(--bg-surface-100) 86%, black 14%);
  color: var(--text-primary);
  cursor: pointer;
}

.list-item-menu-trigger::-webkit-details-marker {
  display: none;
}

.list-item-menu-panel {
  position: absolute;
  top: 2rem;
  right: 0;
  min-width: 10rem;
  border-radius: 0.6rem;
  border: 1px solid var(--bg-surface-200);
  background: var(--bg-surface-100);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.34);
  padding: 0.3rem;
}

.list-item-menu-danger {
  width: 100%;
  border: 0;
  border-radius: 0.45rem;
  background: transparent;
  color: rgb(252 165 165);
  text-align: left;
  font-size: 0.8rem;
  padding: 0.45rem 0.55rem;
}

.list-item-menu-danger:hover {
  background: rgba(239, 68, 68, 0.1);
}
</style>
