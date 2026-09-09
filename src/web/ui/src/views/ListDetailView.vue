<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

          <CountRuntimeBadge :shows="counts.shows" :movies="counts.movies" :total-minutes="totalRuntimeMinutes" />

          <div v-if="canEdit" class="flex gap-2 flex-wrap">
            <button @click="openAddModal" class="btn-ghost text-sm inline-flex items-center whitespace-nowrap border-brand-500/40 text-brand-300 hover:bg-brand-500/10">
              <svg class="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
              </svg>
              Add Item
            </button>
            <button @click="openEditModal" class="btn-ghost text-sm">Edit</button>
            <button @click="openDeleteListDialog" class="btn-ghost text-sm border-red-500/40 text-red-300 hover:bg-red-500/10">Delete</button>
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
        media-type="all"
        :show-status-filter="true"
        :show-provider-status-filter="false"
        :show-genre-filter="true"
        :show-quick-filter-has-upcoming="false"
        :show-quick-filter-new-only="false"
        :show-quick-filter-missing-rating="true"
        :show-quick-filter-in-watchlist="true"
        :show-search="true"
        :show-sort="true"
        :show-direction="true"
        :show-order-sort="true"
        default-sort-key="custom_order"
        :apply-media-type-exclusive-sorts="true"
        search-placeholder="Search list items by title"
        ref="filterBarRef"
        :page="currentPage"
        :sync-url="true"
        @change="onFilterBarChange"
      />

      <Transition name="fade">
        <div v-if="feedbackMsg" class="px-3 py-2 rounded-md text-sm" :class="feedbackKind === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-green-500/10 border border-green-500/20 text-green-400'">
          {{ feedbackMsg }}
        </div>
      </Transition>

      <div v-if="canEdit && items.length" class="flex flex-wrap items-center gap-2">
        <button
          v-if="!reorderMode"
          type="button"
          class="btn-ghost text-sm inline-flex items-center gap-1.5"
          :disabled="!canReorder"
          @click="enterReorderMode"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"/>
          </svg>
          Reorder
        </button>
        <template v-else>
          <button type="button" class="btn-ghost text-sm" :disabled="savingOrder" @click="cancelReorderMode">Cancel</button>
          <button type="button" class="btn-primary text-sm" :disabled="savingOrder" @click="exitReorderMode">
            {{ savingOrder ? 'Saving…' : 'Done' }}
          </button>
          <span class="text-xs text-muted">Drag by handle to reorder. Click Done to save.</span>
          <span v-if="savingOrder" class="text-xs text-brand-300">Saving…</span>
          <span v-else-if="hasReordered" class="text-xs text-amber-300">Unsaved changes</span>
        </template>
      </div>

      <section v-if="items.length && !reorderMode" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <MediaCard
          v-for="item in items"
          :key="item.id"
          :item="item"
          :media-type="item.media_type"
          hide-watchlist-action
          hide-watched-action
          :show-list-remove-action="canEdit"
          :list-context-id="listId()"
          @error="showQuickActionError"
          @list-item-removed="handleListItemRemoved"
        />
      </section>

       <TransitionGroup
         v-if="items.length && reorderMode"
         name="reorder-move"
         tag="section"
         data-reorder-grid
          :class="{ 'reorder-motion': drag }"
         class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4"
       >
        <div
           v-for="(item, index) in reorderDisplayItems"
           :key="item.id"
           :data-reorder-id="String(item.id)"
           class="reorder-card group relative select-none"
           :style="drag?.id === item.id ? { height: `${drag.height}px` } : undefined"
           :class="{ 'drag-placeholder': drag?.id === item.id }"
         >
           <div
            class="reorder-handle absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 inline-flex items-center justify-center gap-2 rounded-full bg-surface-900/85 backdrop-blur border border-white/30 px-6 py-3 text-base font-bold text-white shadow-2xl cursor-grab active:cursor-grabbing"
             role="button"
             tabindex="0"
             :aria-label="`Drag ${item.title || 'media item'}, position ${index + 1}`"
              data-reorder-handle
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16"/>
            </svg>
            #{{ index + 1 }}
          </div>
           <div class="reorder-card-content pointer-events-none">
            <MediaCard
              :item="item"
              :media-type="item.media_type"
              hide-watchlist-action
              hide-watched-action
              :show-list-remove-action="false"
               :list-context-id="listId()"
              @error="showQuickActionError"
            />
          </div>
        </div>
       </TransitionGroup>

       <div
         v-if="drag"
         class="drag-preview"
         :style="{ width: `${drag.width}px`, height: `${drag.height}px`, transform: `translate3d(${drag.position.x}px, ${drag.position.y}px, 0)` }"
         aria-hidden="true"
       >
         <MediaCard
           :item="drag.item"
           :media-type="drag.item.media_type"
           hide-watchlist-action
           hide-watched-action
           :show-list-remove-action="false"
            :list-context-id="listId()"
         />
         <div class="drag-preview-handle inline-flex items-center justify-center gap-2 rounded-full bg-surface-900/85 backdrop-blur border border-white/30 px-6 py-3 text-base font-bold text-white shadow-2xl">
           <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
             <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16"/>
           </svg>
           #{{ (drag.targetIndex ?? 0) + 1 }}
         </div>
       </div>

      <PaginationControls
        v-if="!loading && !reorderMode"
        v-model:page="currentPage"
        :count="count"
        :loaded-count="lastLoadedCount"
        :max-visible-pages="10"
        :disabled="loadingItems"
        @go="currentPage = $event"
      />

      <section v-if="!items.length && !loading && !loadingItems" class="card p-12 text-center">
        <template v-if="hasActiveFilters">
          <p class="text-gray-500 text-lg mb-2">No items match your filters</p>
          <p class="text-gray-600 text-sm mb-6">Try adjusting or clearing the active filters</p>
          <button class="btn-primary" @click="resetFilters">Clear filters</button>
        </template>
        <template v-else>
          <p class="text-gray-500 text-lg mb-2">No items in this list yet</p>
          <p class="text-gray-600 text-sm mb-6">Add movies and shows to get started</p>
          <button v-if="canEdit" @click="openAddModal" class="btn-primary">Add Items</button>
        </template>
      </section>

      <dialog
        ref="editDialog"
        closedby="any"
        class="app-dialog list-dialog w-full max-w-xl rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
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

              <div v-if="collaboratorDraft.length" class="flex flex-wrap gap-2">
                <span
                  v-for="user in collaboratorDraft"
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
        class="app-dialog list-dialog w-full max-w-2xl rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
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

          <div v-if="searching" class="grid grid-cols-3 gap-4 mb-4">
            <div v-for="n in 8" :key="`search-skeleton-${n}`" class="aspect-[2/3] rounded-md skeleton"></div>
          </div>
          <div v-else-if="searchResults.length" class="max-h-[60vh] overflow-y-auto mb-4 pr-1">
            <div class="grid grid-cols-3 gap-4">
              <div v-for="result in searchResults" :key="`${result.media_type}-${result.tmdb_id}`" class="flex h-full flex-col gap-2">
                <div class="flex-1">
                  <MediaCard
                    :item="result"
                    :media-type="result.media_type"
                    :status="result.user_status?.status || undefined"
                    hide-watchlist-action
                    hide-watched-action
                    @error="showQuickActionError"
                  />
                </div>
                <button
                  type="button"
                  class="btn-primary w-full text-xs py-1.5 mt-auto"
                  :disabled="addingResultKey === `${result.media_type}-${result.tmdb_id}`"
                  @click="addSearchResultToList(result)"
                >
                  {{ addingResultKey === `${result.media_type}-${result.tmdb_id}` ? 'Adding...' : 'Add to list' }}
                </button>
              </div>
            </div>
          </div>
          <p v-else-if="searchQuery && !searching" class="text-gray-500 text-sm text-center py-4">No results found</p>

          <div class="flex justify-end">
            <button type="button" @click="closeAddModal" class="btn-ghost">Close</button>
          </div>
        </div>
      </dialog>

      <ConfirmDialog
        ref="deleteListDialog"
        title="Delete this list?"
        message="This permanently deletes the list and removes all list memberships from it."
        confirm-label="Delete"
        cancel-label="Keep list"
        loading-label="Deleting..."
        :loading="deletingList"
        @confirm="confirmDeleteList"
      />

    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, onMounted, onBeforeUnmount, computed, watch, type ComponentPublicInstance } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authAPI, trackingAPI, mediaAPI } from '@/api'
import MediaFilterBar from '@/components/MediaFilterBar.vue'
import MediaCard from '@/components/MediaCard.vue'
import PaginationControls from '@/components/PaginationControls.vue'
import CountRuntimeBadge from '@/components/CountRuntimeBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDateByLocale } from '@/i18n'
import { LIST_PRIVACY, MEDIA_TYPE } from '@/constants/tracking'
import { getApiErrorMessage } from '@/utils/errors'
import { invalidPageRecovery, normalizePagedResponse } from '@/utils/pagination'
import { closeOnDialogBackdropClick } from '@/composables/useDialogLightDismiss'
import { useFlashMessages } from '@/composables/useFlashMessages'
import { useQueryPageSync } from '@/composables/useQueryPageSync'
import { draggable, dropTargetForElements, monitorForElements } from '@atlaskit/pragmatic-drag-and-drop/element/adapter'
import { attachClosestEdge, extractClosestEdge } from '@atlaskit/pragmatic-drag-and-drop-hitbox/closest-edge'
import { reorder } from '@atlaskit/pragmatic-drag-and-drop/reorder'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import type { CustomList, ListItem, MediaResult, UserCard } from '@/types/api'

type ListFilters = {
  search: string; sort: string; direction: 'asc' | 'desc'; mediaType: 'all' | 'movie' | 'tv'; statuses: string[]; providerStatuses: string[]; genres: string[]
  hasUpcoming: boolean; newOnly: boolean; missingRating: boolean; inWatchlist: boolean
}
type FilterChange = { source?: string; filters?: ListFilters }
type FilterBarInstance = ComponentPublicInstance<{ clearAll: () => void }>
type ReorderDrag = { id: number; item: ListItem; sourceIndex: number; targetIndex: number; width: number; height: number; position: { x: number; y: number } }

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const list = ref<CustomList | null>(null)
const items = ref<ListItem[]>([])
const loading = ref(true)
const updating = ref(false)
const loadingItems = ref(false)
const searchQuery = ref('')
const searchResults = ref<(MediaResult & { tmdb_id: number })[]>([])
const searching = ref(false)
const collaboratorQuery = ref('')
const collaboratorResults = ref<UserCard[]>([])
const collaboratorDraft = ref<UserCard[]>([])
const showCollaboratorResults = ref(false)
const searchingUsers = ref(false)
const editDialog = ref<HTMLDialogElement | null>(null)
const addDialog = ref<HTMLDialogElement | null>(null)
const deleteListDialog = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const editNameInput = ref<HTMLInputElement | null>(null)
let collaboratorDebounce: ReturnType<typeof setTimeout> | null = null
const appliedFilters = ref<ListFilters>({
  search: '',
  sort: 'custom_order',
  direction: 'asc',
  mediaType: 'all',
  statuses: [],
  providerStatuses: [],
  genres: [],
  hasUpcoming: false,
  newOnly: false,
  missingRating: false,
  inWatchlist: false,
})
const feedbackMsg = ref('')
const feedbackKind = ref<'success' | 'error'>('success')
const { errorMsg: quickActionError, showError: showQuickActionError } = useFlashMessages()
const deletingList = ref(false)
const addingResultKey = ref('')
const filterBarRef = ref<FilterBarInstance | null>(null)
const count = ref(0)
const lastLoadedCount = ref(0)
const totalRuntimeMinutes = ref(0)
const counts = ref({ shows: 0, movies: 0 })
const currentPage = useQueryPageSync(route)
const hydrated = ref(false)
const reorderMode = ref(false)
const savingOrder = ref(false)
const drag = ref<ReorderDrag | null>(null)
const dragCleanup = ref<(() => void)[]>([])
const hasReordered = ref(false)
const originalOrderIds = ref<number[]>([])

const editForm = ref({
  name: '',
  description: '',
  privacy: LIST_PRIVACY.PUBLIC as CustomList['privacy'],
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

const canReorder = computed(() => {
  if (!canEdit.value) return false
  return items.value.length > 0
})

const reorderDisplayItems = computed(() => {
  const activeDrag = drag.value
  if (!activeDrag || activeDrag.targetIndex === activeDrag.sourceIndex) return items.value
  const next = items.value.filter((item) => item.id !== activeDrag.id)
  const moved = items.value.find((item) => item.id === activeDrag.id)
  if (!moved) return items.value
  next.splice(activeDrag.targetIndex, 0, moved)
  return next
})

const hasActiveFilters = computed(() => {
  const filterState = appliedFilters.value
  return Boolean(
    filterState.search ||
    filterState.sort !== 'custom_order' ||
    filterState.direction !== 'asc' ||
    filterState.mediaType !== 'all' ||
    filterState.statuses.length ||
    filterState.genres.length ||
    filterState.missingRating ||
    filterState.inWatchlist
  )
})

function listId(): string | number {
  const id = route.params.id
  return Array.isArray(id) ? id[0] || '' : id || ''
}

function formatDate(d: string) {
  return formatDateByLocale(d)
}

function showFeedback(message: string, kind: 'success' | 'error' = 'success') {
  feedbackKind.value = kind
  feedbackMsg.value = message
  setTimeout(() => {
    if (feedbackMsg.value === message) {
      feedbackMsg.value = ''
    }
  }, 3500)
}

function privacyClass(privacy: CustomList['privacy']) {
  const classes = {
    [LIST_PRIVACY.PUBLIC]: 'bg-green-500/20 text-green-400',
    [LIST_PRIVACY.PRIVATE]: 'bg-red-500/20 text-red-400',
  }
  return classes[privacy] || ''
}

function onDialogClick(event: MouseEvent, dialog: HTMLDialogElement | null) {
  closeOnDialogBackdropClick(event, dialog)
}

function openEditModal() {
  resetCollaboratorDraft()
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
  resetCollaboratorDraft()
}

function resetCollaboratorDraft() {
  collaboratorDraft.value = [...(list.value?.collaborator_users || [])]
}

function openAddModal() {
  addDialog.value?.showModal()
}

function closeAddModal() {
  if (addDialog.value?.open) {
    addDialog.value.close()
  }
}

function openDeleteListDialog() {
  deleteListDialog.value?.showModal()
}

async function loadList() {
  loading.value = true
  try {
    const data = await trackingAPI.getList(listId())
    if (data) {
      list.value = data
      editForm.value = {
        name: data.name,
        description: data.description || '',
        privacy: data.privacy
      }
    }
  } catch (error) {
    console.error('Failed to load list:', error)
    showFeedback(getApiErrorMessage(error, 'Could not load list.'), 'error')
  } finally {
    loading.value = false
  }
}

async function loadItems() {
  if (reorderMode.value) return
  loadingItems.value = true
  try {
    const filterState = appliedFilters.value
    const params = {
      sort: filterState.sort,
      direction: filterState.direction,
      page: currentPage.value,
      ...(filterState.search ? { search: filterState.search } : {}),
      ...(filterState.mediaType !== 'all' ? { media_type: filterState.mediaType } : {}),
      ...(filterState.statuses.length ? { status: filterState.statuses } : {}),
      ...(filterState.genres.length ? { genres: filterState.genres } : {}),
      ...(filterState.missingRating ? { missing_rating: true } : {}),
      ...(filterState.inWatchlist ? { in_watchlist: true } : {}),
    }
    const data = await trackingAPI.getListItems(listId(), params)
    const paged = normalizePagedResponse<ListItem>(data)
    items.value = paged.items
    count.value = paged.count
    lastLoadedCount.value = paged.loadedCount
    totalRuntimeMinutes.value = Number.isFinite(data.total_runtime_minutes) ? data.total_runtime_minutes ?? 0 : 0
    counts.value = {
      shows: Number.isFinite(data.counts?.shows) ? data.counts?.shows ?? 0 : 0,
      movies: Number.isFinite(data.counts?.movies) ? data.counts?.movies ?? 0 : 0,
    }
  } catch (error) {
    const recoveryPage = invalidPageRecovery(error, currentPage.value)
    if (recoveryPage !== null) {
      currentPage.value = recoveryPage
      return
    }
    showFeedback(getApiErrorMessage(error, 'Could not load list items.'), 'error')
    items.value = []
    count.value = 0
    lastLoadedCount.value = 0
    totalRuntimeMinutes.value = 0
    counts.value = { shows: 0, movies: 0 }
  } finally {
    loadingItems.value = false
  }
}

async function loadAllItemsForReorder() {
  loadingItems.value = true
  try {
    let page = 1
    let all: ListItem[] = []
    let totalCount = 0
    while (true) {
      const data = await trackingAPI.getListItems(listId(), { sort: 'custom_order', direction: 'asc', page })
      const paged = normalizePagedResponse<ListItem>(data)
      all = all.concat(paged.items)
      totalCount = paged.count
      if (!data.next || paged.items.length === 0) break
      // paginated response has next link; continue until all pages
      if (all.length >= totalCount) break
      page += 1
      if (page > 50) break
    }
    items.value = all
    count.value = totalCount
    lastLoadedCount.value = all.length
  } catch (error) {
    showFeedback(getApiErrorMessage(error, 'Could not load list items.'), 'error')
  } finally {
    loadingItems.value = false
  }
}

async function enterReorderMode() {
  if (!canEdit.value) return
  reorderMode.value = true
  hasReordered.value = false
  currentPage.value = 1
  await loadAllItemsForReorder()
  originalOrderIds.value = items.value.map((i) => i.id)
  await nextTick()
  setupReorderDnD()
}

async function exitReorderMode() {
  if (savingOrder.value) return
  cleanupReorderDnD()
  if (!hasReordered.value) {
    reorderMode.value = false
    drag.value = null
    hasReordered.value = false
    await loadItems()
    return
  }
  const ok = await persistOrder()
  if (ok) {
    reorderMode.value = false
    drag.value = null
    await loadItems()
  }
  // on failure stay in reorderMode so user can retry or Cancel
}

function cancelReorderMode() {
  if (savingOrder.value) return
  cleanupReorderDnD()
  reorderMode.value = false
  drag.value = null
  hasReordered.value = false
  // restore original order locally without server call, then reload to ensure consistency
  if (originalOrderIds.value.length) {
    const idToItem = new Map(items.value.map((i) => [i.id, i]))
    const restored = originalOrderIds.value.flatMap((id) => {
      const item = idToItem.get(id)
      return item ? [item] : []
    })
    // append any items that were added after entering reorder (should not happen, but keep)
    const restoredIds = new Set(restored.map((i) => i.id))
    for (const it of items.value) {
      if (!restoredIds.has(it.id)) restored.push(it)
    }
    items.value = restored
  }
  loadItems()
}

function cleanupReorderDnD() {
  dragCleanup.value.splice(0).forEach((cleanup) => cleanup())
  drag.value = null
}

function setupReorderDnD() {
  cleanupReorderDnD()
  const grid = document.querySelector<HTMLElement>('[data-reorder-grid]')
  if (!grid) return
  const itemById = new Map(items.value.map((item) => [String(item.id), item]))
  const cleanups: (() => void)[] = [...grid.querySelectorAll<HTMLElement>('[data-reorder-id]')].flatMap((card) => {
    const cardId = card.dataset.reorderId
    const item = cardId ? itemById.get(cardId) : undefined
    const handle = card.querySelector<HTMLElement>('[data-reorder-handle]')
    if (!item || !handle) return []
    return [
      draggable({ element: handle, getInitialData: () => ({ id: item.id }) }),
      dropTargetForElements({
        element: card,
        canDrop: ({ source }) => source.data.id !== item.id,
        getData: ({ input, element }) => attachClosestEdge(
          { id: item.id },
          { input, element, allowedEdges: ['top', 'bottom'] },
        ),
      }),
    ]
  })
  cleanups.push(monitorForElements({
    onDragStart: ({ source }) => {
      const sourceId = dndItemId(source.data)
      if (sourceId === null) return
      const item = itemById.get(String(sourceId))
      const card = grid.querySelector<HTMLElement>(`[data-reorder-id="${sourceId}"]`)
      const rect = card?.getBoundingClientRect()
      if (!item || !rect) return
      const sourceIndex = items.value.findIndex((candidate) => candidate.id === item.id)
      drag.value = { id: item.id, item, sourceIndex, targetIndex: sourceIndex, width: rect.width, height: rect.height, position: { x: rect.left, y: rect.top } }
    },
    onDrag: ({ location }) => {
      const activeDrag = drag.value
      if (!activeDrag) return
      const input = location.current.input
      activeDrag.position = { x: input.clientX - activeDrag.width / 2, y: input.clientY - activeDrag.height / 2 }
      const target = location.current.dropTargets[0]
      if (!target) return
      const targetId = dndItemId(target.data)
      if (targetId === null) return
      const withoutDragged = items.value.filter((item) => item.id !== activeDrag.id)
      const targetPosition = withoutDragged.findIndex((item) => item.id === targetId)
      if (targetPosition < 0) return
      const edge = extractClosestEdge(target.data)
      const insertionIndex = targetPosition + (edge === 'bottom' ? 1 : 0)
      if (activeDrag.targetIndex !== insertionIndex) {
        activeDrag.targetIndex = insertionIndex
        hasReordered.value = true
      }
    },
    onDrop: () => {
      const activeDrag = drag.value
      if (activeDrag) {
        const finishIndex = Math.min(activeDrag.targetIndex, items.value.length - 1)
        items.value = reorder({ list: items.value, startIndex: activeDrag.sourceIndex, finishIndex })
      }
      drag.value = null
    },
  }))
  dragCleanup.value = cleanups
}

function dndItemId(data: Record<string, unknown>): number | null {
  return typeof data.id === 'number' ? data.id : null
}

async function persistOrder() {
  if (savingOrder.value) return false
  savingOrder.value = true
  const orderedIds = items.value.map((i) => i.id)
  const snapshot = [...items.value]
  if (!orderedIds.length) {
    showFeedback('Nothing to save.', 'error')
    savingOrder.value = false
    return false
  }
  if (!route.params.id) {
    showFeedback('Could not save order: missing list id.', 'error')
    savingOrder.value = false
    return false
  }
  try {
    await trackingAPI.reorderList(listId(), orderedIds)
    showFeedback('Order saved.')
    hasReordered.value = false
    originalOrderIds.value = [...orderedIds]
    return true
  } catch (error) {
    showFeedback(getApiErrorMessage(error, 'Could not save order.'), 'error')
    try {
      await loadAllItemsForReorder()
    } catch {
      // ignore reload failure, fallback to snapshot
    }
    if (items.value.length === 0) items.value = snapshot
    return false
  } finally {
    savingOrder.value = false
  }
}

function resetFilters() {
  filterBarRef.value?.clearAll()
}

function onFilterBarChange(payload: FilterChange) {
  const next = payload.filters
  if (!next) return

  const didChange = JSON.stringify(appliedFilters.value) !== JSON.stringify(next)
  appliedFilters.value = next
  hydrated.value = true

  if (didChange && payload?.source === 'interaction') {
    currentPage.value = 1
  }
}

async function updateList() {
  updating.value = true
  try {
    await trackingAPI.updateList(listId(), {
      ...editForm.value,
      collaborator_ids: collaboratorDraft.value.map((user) => Number(user.id)),
    })
    await loadList()
    closeEditModal()
  } catch (error) {
    console.error('Failed to update list:', error)
    showFeedback(getApiErrorMessage(error, 'Could not update list.'), 'error')
  } finally {
    updating.value = false
  }
}

async function confirmDeleteList() {
  if (deletingList.value) {
    return
  }
  deletingList.value = true
  try {
    await trackingAPI.deleteList(listId())
    deleteListDialog.value?.close()
    router.push('/lists')
  } catch (error) {
    console.error('Failed to delete list:', error)
    showFeedback(getApiErrorMessage(error, 'Could not delete list.'), 'error')
  } finally {
    deletingList.value = false
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
        tmdb_id: 'tmdb_id' in item && typeof item.tmdb_id === 'number' ? item.tmdb_id : item.id,
      }))
    }
  } catch (error) {
    console.error('Search failed:', error)
  } finally {
    searching.value = false
  }
}

function handleListItemAdded() {
  searchQuery.value = ''
  searchResults.value = []
  closeAddModal()
  if (reorderMode.value) {
    loadAllItemsForReorder()
  } else {
    loadItems()
  }
  showFeedback('Item added to list.')
}

async function addSearchResultToList(result: MediaResult & { tmdb_id: number }) {
  const tmdbId = result.tmdb_id || result.id
  if (!tmdbId || !listId()) {
    showFeedback('Could not add item to list.', 'error')
    return
  }
  const requestKey = `${result.media_type}-${tmdbId}`
  if (addingResultKey.value) {
    return
  }
  addingResultKey.value = requestKey
  try {
    await trackingAPI.addToList(listId(), {
      media_type: result.media_type,
      tmdb_id: tmdbId,
    })
    handleListItemAdded()
  } catch (error) {
    showFeedback(getApiErrorMessage(error, 'Could not add item to list.'), 'error')
  } finally {
    addingResultKey.value = ''
  }
}

function handleListItemRemoved() {
  if (reorderMode.value) {
    loadAllItemsForReorder()
  } else {
    loadItems()
  }
  showFeedback('Item removed from list.')
}

function addCollaborator(user: UserCard) {
  if (!isOwner.value || !user.id) return
  if (!collaboratorDraft.value.some((entry) => Number(entry.id) === Number(user.id))) {
    collaboratorDraft.value.push(user)
  }
  collaboratorQuery.value = ''
  collaboratorResults.value = []
  showCollaboratorResults.value = false
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
      const existingIds = new Set(collaboratorDraft.value.map((entry) => entry.id))
      collaboratorResults.value = (data || []).filter((entry) => !existingIds.has(entry.id))
    } catch (error) {
      collaboratorResults.value = []
      console.error('Failed to search users:', error)
    } finally {
      searchingUsers.value = false
    }
  }, 250)
}

function removeCollaborator(userId: number) {
  if (!isOwner.value) return
  collaboratorDraft.value = collaboratorDraft.value.filter((user) => Number(user.id) !== Number(userId))
}

onMounted(async () => {
  await loadList()
  if (!hydrated.value) hydrated.value = true
})

onBeforeUnmount(() => {
  cleanupReorderDnD()
})

watch(
  [appliedFilters, currentPage, hydrated],
  async () => {
    if (!hydrated.value) return
    if (reorderMode.value) return
    await loadItems()
  },
  { deep: true, immediate: true }
)
</script>

<style scoped>
.list-dialog {
  inset: 0;
  max-height: calc(100vh - 2rem);
}
.reorder-card {
  transition: opacity 0.15s, box-shadow 0.15s;
}
.reorder-motion .reorder-move-move {
  transition: transform 0.18s cubic-bezier(.2,.8,.2,1);
}
.reorder-handle {
  cursor: grab;
  touch-action: none;
}
.reorder-handle:active {
  cursor: grabbing;
}
.drag-preview {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 50;
  pointer-events: none;
  transform-origin: top left;
  filter: drop-shadow(0 22px 20px rgb(0 0 0 / 0.35));
  opacity: 0.94;
  will-change: transform;
  overflow: visible;
}
.drag-preview-handle {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 2;
  transform: translate(-50%, -50%);
  white-space: nowrap;
}
.drag-placeholder {
  min-height: 1px;
  pointer-events: none;
  border: 1px dashed rgb(139 92 246 / 0.45);
  border-radius: 0.5rem;
  background: rgb(139 92 246 / 0.08);
}
.drag-placeholder .reorder-handle,
.drag-placeholder .reorder-card-content {
  visibility: hidden;
}
</style>
