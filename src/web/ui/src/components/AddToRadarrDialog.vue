<template>
  <dialog
    ref="dialogRef"
    closedby="any"
    class="app-dialog w-full max-w-lg rounded-xl border border-surface-200 bg-surface-100 p-0 text-primary"
    :aria-labelledby="titleId"
    @click="onDialogClick"
  >
    <div class="p-5 md:p-6">
      <div class="mb-4 flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 :id="titleId" class="text-lg font-display text-primary font-semibold">{{ heading }}</h2>
          <p class="text-xs text-muted mt-1 truncate">{{ title }}</p>
        </div>
        <button type="button" class="text-muted hover:text-primary" :aria-label="t('common_cancel')" @click="close">
          <X class="w-5 h-5" aria-hidden="true" />
        </button>
      </div>

      <div v-if="status === 'loading'" class="space-y-3" aria-busy="true">
        <div v-for="n in 4" :key="n" class="h-10 skeleton rounded-md"></div>
      </div>

      <LoadError v-else-if="status === 'error'" :message="loadError" @retry="load" />

      <div v-else-if="status === 'exists'" class="space-y-4">
        <div class="rounded-lg border border-surface-200 bg-surface px-4 py-3">
          <p class="text-sm text-primary">{{ t('radarr_already_added') }}</p>
          <p v-if="existing?.path" class="text-xs text-muted mt-1 break-all">{{ existing.path }}</p>
        </div>
        <div class="flex flex-col gap-3 sm:flex-row">
          <a
            v-if="existing?.url"
            :href="existing.url"
            target="_blank"
            rel="noopener noreferrer"
            class="btn-ghost flex-1 inline-flex items-center justify-center gap-2 text-center"
          >
            {{ t('radarr_open') }}
            <ExternalLink class="w-4 h-4" aria-hidden="true" />
          </a>
          <button type="button" class="btn-ghost flex-1 border-red-500/40 text-red-300 hover:bg-red-500/10" @click="startRemove">
            {{ t('radarr_remove') }}
          </button>
        </div>
      </div>

      <form v-else-if="status === 'remove'" class="space-y-4" @submit.prevent="remove">
        <p class="text-sm text-primary">{{ t('radarr_remove_confirm') }}</p>
        <div class="space-y-2">
          <label class="flex items-center gap-2 text-sm text-secondary">
            <input v-model="removeForm.delete_files" type="checkbox" class="accent-brand-500">
            {{ t('radarr_delete_files') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-secondary">
            <input v-model="removeForm.add_import_exclusion" type="checkbox" class="accent-brand-500">
            {{ t('radarr_add_exclusion') }}
          </label>
        </div>

        <p v-if="submitError" role="alert" class="px-3 py-2 rounded-md text-sm bg-red-500/10 border border-red-500/20 text-red-400">{{ submitError }}</p>

        <div class="flex gap-3 pt-1">
          <button type="button" class="btn-ghost flex-1" :disabled="submitting" @click="status = 'exists'">{{ t('radarr_back') }}</button>
          <button
            type="submit"
            class="btn-ghost flex-1 border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="submitting"
          >
            {{ submitting ? t('radarr_removing') : t('radarr_remove_action') }}
          </button>
        </div>
      </form>

      <form v-else class="space-y-4" @submit.prevent="submit">
        <label class="block">
          <span class="block text-xs text-muted mb-1">{{ t('radarr_quality_profile') }}</span>
          <select v-model="form.quality_profile_id" class="input rounded-md text-sm" required>
            <option v-for="profile in options?.quality_profiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
          </select>
        </label>

        <label class="block">
          <span class="block text-xs text-muted mb-1">{{ t('radarr_root_folder') }}</span>
          <select v-model="form.root_folder_path" class="input rounded-md text-sm" required>
            <option v-for="folder in options?.root_folders" :key="folder.path" :value="folder.path">{{ folderLabel(folder) }}</option>
          </select>
        </label>

        <label class="block">
          <span class="block text-xs text-muted mb-1">{{ t('radarr_minimum_availability') }}</span>
          <select v-model="form.minimum_availability" class="input rounded-md text-sm">
            <option v-for="value in AVAILABILITY_OPTIONS" :key="value" :value="value">{{ t(AVAILABILITY_LABEL_KEYS[value]) }}</option>
          </select>
        </label>

        <fieldset v-if="options?.tags.length">
          <legend class="block text-xs text-muted mb-1">{{ t('radarr_tags') }}</legend>
          <div class="flex flex-wrap gap-x-4 gap-y-1">
            <label v-for="tag in options.tags" :key="tag.id" class="inline-flex items-center gap-2 text-sm text-secondary">
              <input v-model="form.tags" type="checkbox" :value="tag.id" class="accent-brand-500">
              {{ tag.label }}
            </label>
          </div>
        </fieldset>

        <div class="space-y-2">
          <label class="flex items-center gap-2 text-sm text-secondary">
            <input v-model="form.monitored" type="checkbox" class="accent-brand-500">
            {{ t('radarr_monitored') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-secondary">
            <input v-model="form.search_for_movie" type="checkbox" class="accent-brand-500">
            {{ t('radarr_search_on_add') }}
          </label>
        </div>

        <p v-if="submitError" role="alert" class="px-3 py-2 rounded-md text-sm bg-red-500/10 border border-red-500/20 text-red-400">{{ submitError }}</p>

        <div class="flex gap-3 pt-1">
          <button type="button" class="btn-ghost flex-1" @click="close">{{ t('common_cancel') }}</button>
          <button type="submit" class="btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed" :disabled="submitting || !canSubmit">
            {{ submitting ? t('radarr_adding') : t('radarr_add') }}
          </button>
        </div>
      </form>
    </div>
  </dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, useId } from 'vue'
import { ExternalLink, X } from '@lucide/vue'
import { integrationsAPI } from '@/api'
import LoadError from '@/components/LoadError.vue'
import { INTEGRATION_BRANDS } from '@/constants/integrations'
import { closeOnDialogBackdropClick } from '@/composables/useDialogLightDismiss'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'
import { useI18n, type MessageKey } from '@/i18n'
import { getApiErrorMessage } from '@/utils/errors'
import type { ApiError, ArrItemState, ArrOptions, RadarrAddPayload, RadarrMinimumAvailability } from '@/types/api'

type Status = 'loading' | 'error' | 'exists' | 'remove' | 'form'

const AVAILABILITY_OPTIONS: RadarrMinimumAvailability[] = ['announced', 'inCinemas', 'released']
const AVAILABILITY_LABEL_KEYS: Record<RadarrMinimumAvailability, MessageKey> = {
  announced: 'radarr_availability_announced',
  inCinemas: 'radarr_availability_in_cinemas',
  released: 'radarr_availability_released',
}

const props = defineProps<{ tmdbId: string | number; title: string }>()
const emit = defineEmits<{ added: []; removed: []; synced: [state: ArrItemState] }>()

const { t } = useI18n()
const { next: nextRequest } = useLatestRequest()
const dialogRef = ref<HTMLDialogElement | null>(null)
const titleId = useId()

const status = ref<Status>('loading')
const loadError = ref('')
const submitError = ref('')
const submitting = ref(false)
const options = ref<ArrOptions | null>(null)
const existing = ref<ArrItemState | null>(null)
const removeForm = reactive({ delete_files: false, add_import_exclusion: false })
const form = reactive({
  quality_profile_id: null as number | null,
  root_folder_path: '',
  minimum_availability: 'released' as RadarrMinimumAvailability,
  monitored: true,
  search_for_movie: true,
  tags: [] as number[],
})

const canSubmit = computed(() => form.quality_profile_id !== null && form.root_folder_path !== '')

const HEADING_KEYS: Partial<Record<Status, MessageKey>> = {
  form: 'radarr_dialog_title',
  exists: 'radarr_in_button',
  remove: 'radarr_remove',
}
const heading = computed(() => {
  const key = HEADING_KEYS[status.value]
  return key ? t(key) : INTEGRATION_BRANDS.radarr.name
})

function folderLabel(folder: ArrOptions['root_folders'][number]) {
  if (folder.free_space === null) return folder.path
  const freeGb = Math.round(folder.free_space / 1024 ** 3)
  return t('radarr_folder_free_space', { path: folder.path, free: freeGb })
}

function resetForm(loaded: ArrOptions) {
  form.quality_profile_id = loaded.quality_profiles[0]?.id ?? null
  form.root_folder_path = loaded.root_folders[0]?.path ?? ''
  form.minimum_availability = 'released'
  form.monitored = true
  form.search_for_movie = true
  form.tags = []
}

async function load() {
  const signal = nextRequest()
  status.value = 'loading'
  submitError.value = ''
  try {
    const [state, loaded] = await Promise.all([
      integrationsAPI.getRadarrMovie(props.tmdbId, { signal }),
      integrationsAPI.getRadarrOptions({ signal }),
    ])
    options.value = loaded
    existing.value = state
    resetForm(loaded)
    status.value = state.added ? 'exists' : 'form'
    emit('synced', state)
  } catch (error) {
    if (isAbortError(error)) return
    loadError.value = getApiErrorMessage(error, t('radarr_load_failed'))
    status.value = 'error'
  }
}

async function submit() {
  const qualityProfileId = form.quality_profile_id
  if (submitting.value || qualityProfileId === null || !canSubmit.value) return
  submitting.value = true
  submitError.value = ''
  const payload: RadarrAddPayload = { ...form, quality_profile_id: qualityProfileId, tags: [...form.tags] }
  try {
    emit('synced', await integrationsAPI.addRadarrMovie(props.tmdbId, payload))
    emit('added')
    close()
  } catch (error) {
    if ((error as ApiError).status === 409) {
      await load()
    } else {
      submitError.value = getApiErrorMessage(error, t('radarr_add_failed'))
    }
  } finally {
    submitting.value = false
  }
}

function startRemove() {
  removeForm.delete_files = false
  removeForm.add_import_exclusion = false
  submitError.value = ''
  status.value = 'remove'
}

async function remove() {
  if (submitting.value) return
  submitting.value = true
  submitError.value = ''
  try {
    emit('synced', await integrationsAPI.removeRadarrMovie(props.tmdbId, { ...removeForm }))
    emit('removed')
    close()
  } catch (error) {
    if ((error as ApiError).status === 404) {
      await load()
    } else {
      submitError.value = getApiErrorMessage(error, t('radarr_remove_failed'))
    }
  } finally {
    submitting.value = false
  }
}

function showModal() {
  dialogRef.value?.showModal()
  void load()
}

function close() {
  if (dialogRef.value?.open) {
    dialogRef.value.close()
  }
}

function onDialogClick(event: MouseEvent) {
  closeOnDialogBackdropClick(event, dialogRef.value)
}

defineExpose({ showModal, close })
</script>
