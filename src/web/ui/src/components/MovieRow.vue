<template>
  <article class="card p-3 md:p-4">
    <div class="flex gap-3 md:gap-4">
      <RouterLink :to="`/movies/${item.tmdb_id}`" class="w-[90px] h-[135px] rounded-md overflow-hidden bg-surface-200 flex-shrink-0 border border-surface-200">
        <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title" class="w-full h-full object-cover" loading="lazy">
      </RouterLink>

      <div class="flex-1 min-w-0">
        <div class="show-meta-row">
          <RouterLink :to="`/movies/${item.tmdb_id}`" class="block text-xl leading-tight font-display text-primary font-semibold hover:text-brand-400 truncate" :title="item.title">{{ item.title }}</RouterLink>

          <div class="show-headline-meta">
            <details ref="menuRef" class="control-menu">
              <summary class="row-pill-trigger" title="Manage" aria-label="Manage movie">
                <span>Manage</span>
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                </svg>
              </summary>
              <div class="control-panel right-0 w-52 p-1.5 menu-panel">
                <button type="button" class="control-option" :disabled="busy" @click="openRateDialog">
                  Rate
                </button>
                <button type="button" class="control-option" :disabled="busy" @click="toggleListPopover">
                  Add to list
                </button>
              </div>
            </details>
            <AddToListPopover
              v-if="listPopoverOpen"
              :media-type="MEDIA_TYPE.MOVIE"
              :tmdb-id="item.tmdb_id"
              :start-open="true"
              @added="onListAdded"
            />
          </div>
        </div>

        <div class="mt-1 flex items-center gap-1.5 flex-wrap">
          <span class="status-pill" :class="statusClass(item.status)">{{ statusText(item.status) }}</span>
          <UserRating v-if="item.user_rating" :value="item.user_rating" size="xs" />
          <RatingBadge v-if="hasProviderRating(item.vote_average)" :value="item.vote_average" size="xs" out-of-ten />
        </div>

        <p class="mt-2 text-xs text-muted">
          {{ releaseYear(item) }}<template v-if="releaseYear(item)"> · </template>{{ runtimeText(item) }}
        </p>

        <p class="mt-1.5 text-[11px] text-muted truncate">{{ genresText(item) }}</p>

        <p v-if="item.last_watched_at" class="mt-1.5 text-[11px] text-muted">Watched {{ formatCompactDate(item.last_watched_at) }}</p>
      </div>
    </div>

    <dialog
      ref="rateDialog"
      closedby="any"
      class="app-dialog progress-dialog w-full max-w-md rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
      :aria-labelledby="`movie-rate-title-${item.tmdb_id}`"
      @click="onDialogClick($event, rateDialog)"
      @close="onRateDialogClose"
    >
      <div class="p-5 md:p-6">
        <div class="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 :id="`movie-rate-title-${item.tmdb_id}`" class="text-lg font-display text-primary font-semibold">Rate movie</h2>
            <p class="text-xs text-muted mt-1">{{ item.title || 'Select your score' }}</p>
          </div>
          <button type="button" class="text-muted hover:text-primary" @click="closeRateDialog">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="rounded-lg border border-surface-200 bg-surface px-3 py-3">
          <p class="text-xs text-muted mb-2">Your rating</p>
          <StarRating v-model="rating" @update:modelValue="submitRating" />
        </div>

        <p v-if="savingRating" class="mt-3 text-xs text-muted">Saving rating...</p>
      </div>
    </dialog>
  </article>
</template>

<script setup>
import { ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { trackingAPI } from '@/api'
import AddToListPopover from '@/components/AddToListPopover.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import StarRating from '@/components/StarRating.vue'
import UserRating from '@/components/UserRating.vue'
import { MEDIA_TYPE } from '@/constants/tracking'
import { getApiErrorMessage } from '@/utils/errors'
import { closeOnDialogBackdropClick } from '@/composables/useDialogLightDismiss'
import { formatIsoAsDDMMYYYY } from '@/utils/temporal'

const props = defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(['changed', 'error'])

const busy = ref(false)
const menuRef = ref(null)
const rateDialog = ref(null)
const rating = ref(0)
const savingRating = ref(false)
const listPopoverOpen = ref(false)

onClickOutside(menuRef, () => {
  if (!menuRef.value?.open) return
  menuRef.value.open = false
})

function closeMenu() {
  menuRef.value?.removeAttribute('open')
}

function onDialogClick(event, dialogRef) {
  closeOnDialogBackdropClick(event, dialogRef)
}

function openRateDialog() {
  rating.value = Number(props.item.user_rating) || 0
  closeMenu()
  rateDialog.value?.showModal()
}

function closeRateDialog() {
  rateDialog.value?.close()
}

function onRateDialogClose() {
  savingRating.value = false
  rating.value = 0
}

async function submitRating(score) {
  if (!Number.isInteger(score) || score < 1 || score > 10 || savingRating.value) {
    return
  }
  savingRating.value = true
  try {
    await trackingAPI.rate({ media_type: MEDIA_TYPE.MOVIE, tmdb_id: props.item.tmdb_id, score })
    closeRateDialog()
    emit('changed')
  } catch (error) {
    emit('error', getApiErrorMessage(error, 'Could not submit rating.'))
  } finally {
    savingRating.value = false
  }
}

function toggleListPopover() {
  closeMenu()
  listPopoverOpen.value = !listPopoverOpen.value
}

async function onListAdded() {
  listPopoverOpen.value = false
  emit('changed')
}

function hasProviderRating(value) {
  const ratingValue = Number(value)
  return Number.isFinite(ratingValue) && ratingValue > 0
}

function formatCompactDate(value) {
  if (!value) return '--'
  return formatIsoAsDDMMYYYY(value) || '--'
}

function releaseYear(item) {
  const year = String(item?.release_date || '').slice(0, 4)
  return /^\d{4}$/.test(year) ? year : ''
}

function runtimeText(item) {
  const runtime = Number(item?.runtime)
  if (!Number.isFinite(runtime) || runtime <= 0) return '-- min'
  return `${runtime} min`
}

function statusClass(value) {
  if (value === 'watched') return 'status-watched'
  if (value === 'dropped') return 'status-dropped'
  return 'status-default'
}

function statusText(value) {
  if (value === 'plan_to_watch') return 'Plan to watch'
  if (value === 'watched') return 'Watched'
  if (value === 'dropped') return 'Dropped'
  return value
}

function genresText(item) {
  const values = Array.isArray(item?.genres) ? item.genres : []
  return values.join(', ')
}
</script>

<style scoped>
.control-menu {
  position: relative;
}

.control-menu[open] {
  z-index: 80;
}

.control-panel {
  position: absolute;
  z-index: 60;
  margin-top: 0.35rem;
  border-radius: 0.75rem;
  border: 1px solid var(--bg-surface-200);
  background: var(--bg-surface-100);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
}

.control-option {
  width: 100%;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  font-size: 0.8125rem;
  border-radius: 0.5rem;
  padding: 0.5rem 0.6rem;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
}

.control-option:hover {
  background: var(--bg-surface-200);
  color: var(--text-primary);
}

.control-option-danger {
  color: var(--text-secondary);
}

.control-option-danger:hover,
.control-option-danger:focus-visible {
  color: var(--text-primary);
}

.row-pill-trigger {
  list-style: none;
  min-height: 1.8rem;
  border: 1px solid var(--bg-surface-200);
  background: var(--bg-surface-200);
  border-radius: 0.45rem;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.55rem;
  font-size: 0.82rem;
  line-height: 1;
  cursor: pointer;
}

.row-pill-trigger::-webkit-details-marker {
  display: none;
}

.menu-panel {
  margin-top: 0.2rem;
}

.row-pill-trigger:hover,
.row-pill-trigger:focus-visible {
  background: color-mix(in srgb, var(--brand-500) 14%, var(--bg-surface-200));
  color: var(--text-primary);
}

.show-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.6rem;
}

.show-headline-meta {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  flex-shrink: 0;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 0.45rem;
  padding: 0.28rem 0.5rem;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  border: 1px solid transparent;
}

.status-default { background: var(--bg-surface-200); color: var(--text-secondary); border-color: var(--bg-surface-300); }
.status-watched {
  background: color-mix(in srgb, #86efac 18%, var(--bg-surface-100));
  color: var(--text-secondary);
  border-color: color-mix(in srgb, #22c55e 40%, var(--bg-surface-300));
}
.status-dropped { background: color-mix(in srgb, var(--action-danger) 14%, var(--bg-surface-100)); color: var(--text-secondary); border-color: color-mix(in srgb, var(--action-danger) 45%, var(--bg-surface-300)); }

@media (max-width: 767px) {
  .show-headline-meta {
    margin-left: auto;
  }
}
</style>
