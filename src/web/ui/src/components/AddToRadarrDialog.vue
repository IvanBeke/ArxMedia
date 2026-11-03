<template>
  <ArrDialogShell ref="shell" :heading="heading" :title="title">
    <div v-if="status === 'loading'" class="space-y-3" aria-busy="true">
      <div v-for="n in 4" :key="n" class="h-10 skeleton rounded-md"></div>
    </div>

    <LoadError v-else-if="status === 'error'" :message="loadError" @retry="load" />

    <ArrExistsPanel
      v-else-if="status === 'exists'"
      :message="t('radarr_already_added')"
      :path="existing?.path"
      :url="existing?.url"
      :open-label="t('radarr_open')"
      :remove-label="t('radarr_remove')"
      @remove="status = 'remove'"
    />

    <ArrRemoveForm
      v-else-if="status === 'remove'"
      :message="t('radarr_remove_confirm')"
      :delete-files-label="t('radarr_delete_files')"
      :submitting="submitting"
      :error="submitError"
      @back="status = 'exists'"
      @submit="remove"
    />

    <form v-else class="space-y-4" @submit.prevent="submit">
      <label class="block">
        <span class="block text-xs text-muted mb-1">{{ t('arr_quality_profile') }}</span>
        <select v-model="form.quality_profile_id" class="input rounded-md text-sm" required>
          <option v-for="profile in options?.quality_profiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
        </select>
      </label>

      <label class="block">
        <span class="block text-xs text-muted mb-1">{{ t('arr_root_folder') }}</span>
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
        <legend class="block text-xs text-muted mb-1">{{ t('arr_tags') }}</legend>
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
          {{ t('arr_monitored') }}
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
          {{ submitting ? t('arr_adding') : t('radarr_add') }}
        </button>
      </div>
    </form>
  </ArrDialogShell>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { integrationsAPI } from '@/api'
import ArrDialogShell from '@/components/ArrDialogShell.vue'
import ArrExistsPanel from '@/components/ArrExistsPanel.vue'
import ArrRemoveForm from '@/components/ArrRemoveForm.vue'
import LoadError from '@/components/LoadError.vue'
import { INTEGRATION_BRANDS } from '@/constants/integrations'
import { isAbortError, useLatestRequest } from '@/composables/useLatestRequest'
import { useI18n, type MessageKey } from '@/i18n'
import { getApiErrorMessage } from '@/utils/errors'
import type { ApiError, ArrItemState, ArrOptions, ArrRemovePayload, RadarrAddPayload, RadarrMinimumAvailability } from '@/types/api'

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
const shell = ref<InstanceType<typeof ArrDialogShell> | null>(null)

const status = ref<Status>('loading')
const loadError = ref('')
const submitError = ref('')
const submitting = ref(false)
const options = ref<ArrOptions | null>(null)
const existing = ref<ArrItemState | null>(null)
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
  form: 'radarr_add_button',
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
  return t('arr_folder_free_space', { path: folder.path, free: freeGb })
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

async function remove(removeOptions: ArrRemovePayload) {
  if (submitting.value) return
  submitting.value = true
  submitError.value = ''
  try {
    emit('synced', await integrationsAPI.removeRadarrMovie(props.tmdbId, removeOptions))
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
  shell.value?.showModal()
  void load()
}

function close() {
  shell.value?.close()
}

defineExpose({ showModal, close })
</script>
