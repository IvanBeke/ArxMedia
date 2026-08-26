<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <header class="mb-6">
      <h1 class="font-display text-3xl text-primary font-semibold tracking-tight">Import Data</h1>
      <p class="text-sm text-muted mt-1">Import from Trakt ZIP exports, Yamtrack CSV exports, or JSON backups created by ArxMedia.</p>
    </header>

    <div class="space-y-6">
      <section class="card p-5">
        <h2 class="text-primary font-semibold text-xl mb-1">Import Data</h2>
        <p class="text-sm text-muted mb-4">Use the correct import type to avoid format errors.</p>
        <div class="grid md:grid-cols-2 gap-3">
          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">Import Trakt ZIP</h3>
            </div>
            <input
              ref="zipInput"
              type="file"
              class="input text-sm"
              accept=".zip,application/zip"
              aria-label="Import Trakt ZIP"
              @change="clearZipError"
            />
            <p class="text-xs text-muted mt-2">For Trakt export ZIP files only.</p>
            <p v-if="zipError" class="text-xs text-red-400 mt-2">{{ zipError }}</p>
            <div class="mt-3">
              <button class="btn-primary text-sm" @click="startZipImport">Upload ZIP</button>
            </div>
          </div>
          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">Import Yamtrack CSV</h3>
            </div>
            <input
              ref="yamtrackInput"
              type="file"
              class="input text-sm"
              accept=".csv,text/csv"
              aria-label="Import Yamtrack CSV"
              @change="clearYamtrackError"
            />
            <p class="text-xs text-muted mt-2">For Yamtrack CSV exports. Imports TMDB rows only.</p>
            <p v-if="yamtrackError" class="text-xs text-red-400 mt-2">{{ yamtrackError }}</p>
            <div class="mt-3">
              <button class="btn-primary text-sm" @click="startYamtrackImport">Upload CSV</button>
            </div>
          </div>
          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">Import ArxMedia JSON</h3>
            </div>
            <input
              ref="jsonInput"
              type="file"
              class="input text-sm"
              accept=".json,application/json"
              aria-label="Import ArxMedia JSON"
              @change="clearJsonError"
            />
            <p class="text-xs text-muted mt-2">For JSON files exported from this app.</p>
            <p v-if="jsonError" class="text-xs text-red-400 mt-2">{{ jsonError }}</p>
            <div class="mt-3">
              <button class="btn-primary text-sm" @click="startJsonImport">Upload JSON</button>
            </div>
          </div>
        </div>
      </section>

      <section class="card p-5">
        <h2 class="text-primary font-semibold text-xl mb-3">Recent Jobs</h2>
        <div v-if="recentJobs.length" class="space-y-3">
          <div
            v-for="recentJob in recentJobs"
            :key="recentJob.id"
            class="rounded-lg border border-surface-200 bg-surface-100 p-3"
            :class="recentJob.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION ? 'cursor-pointer hover:bg-surface-200/70' : ''"
            @click="openAwaitingJobModal(recentJob)"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm text-secondary">Started: <span class="text-primary">{{ formatDateTime(recentJob.created_at) }}</span></p>
              <span class="text-xs font-semibold uppercase tracking-wide" :class="statusClass(recentJob.status)">{{ humanStatus(recentJob.status) }}</span>
            </div>
            <p class="text-sm text-secondary mt-1">Progress: <span class="text-primary">{{ recentJob.processed_items }} / {{ progressTotal(recentJob) }}</span><span v-if="stageLabel(recentJob)" class="text-muted"> · {{ stageLabel(recentJob) }}</span></p>
            <p v-if="recentJob.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION" class="text-xs text-amber-400 mt-1">Click to pick import mode</p>
            <p v-if="recentJob.error_message" class="text-sm text-red-400 mt-1">{{ recentJob.error_message }}</p>
          </div>
        </div>
        <p v-else class="text-sm text-muted">No import jobs from the last 7 days.</p>
      </section>

      <section class="card p-5">
        <h2 class="text-primary font-semibold text-xl mb-1">Export File</h2>
        <p class="text-sm text-muted mb-4">Create a JSON backup export of your data.</p>
        <button class="btn-primary text-sm" @click="startExport">Create export</button>
        <a
          v-if="latestExport?.output_url"
          :href="latestExport.output_url"
          target="_blank"
          class="ml-4 text-sm text-brand-400 hover:text-brand-300"
        >
          Download latest export
        </a>
      </section>
    </div>

    <div v-if="showImportModeModal" class="fixed inset-0 z-[150] flex items-center justify-center p-4">
      <button
        type="button"
        class="absolute inset-0 bg-black/60"
        aria-label="Close import mode modal"
        @click="closeImportModal"
      ></button>
      <div class="relative w-full max-w-2xl rounded-xl border border-surface-200 bg-surface p-5 shadow-xl">
        <div class="flex items-start justify-between gap-4 mb-4">
          <div>
            <p class="text-xs uppercase tracking-wide text-muted">Last step: pick a mode</p>
            <h3 class="text-primary text-2xl font-display font-semibold">How should we import it?</h3>
            <p class="text-sm text-muted mt-1">Choose how imported data interacts with what you already track here.</p>
          </div>
          <button class="text-muted hover:text-primary" @click="closeImportModal">X</button>
        </div>

        <div v-if="modalIsPreparing" class="rounded-lg border border-surface-200 bg-surface-100 p-6 mb-4 text-center">
          <div class="inline-block h-8 w-8 animate-spin rounded-full border-2 border-surface-300 border-t-brand-500"></div>
          <p class="text-primary font-semibold mt-3">Preparing import summary...</p>
          <p class="text-sm text-muted mt-1">We are scanning the uploaded file to compute totals.</p>
        </div>

        <div v-else-if="modalCanConfirm" class="rounded-lg border border-surface-200 bg-surface-100 p-3 mb-4">
          <p class="text-sm text-secondary">Items found</p>
          <p class="text-lg text-primary font-semibold">{{ modalSummary.total }}</p>
          <p class="text-xs text-muted mt-1">
            History: {{ modalSummary.history }} | Watchlist: {{ modalSummary.watchlist }} | Ratings: {{ modalSummary.ratings }}
          </p>
        </div>

        <div v-else-if="modalJob?.status === DATA_TRANSFER_STATUS.FAILED" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 mb-4">
          <p class="text-sm text-red-300">Import analysis failed.</p>
          <p class="text-xs text-red-200 mt-1">{{ modalJob?.error_message || 'Unknown error while reading import contents.' }}</p>
        </div>

        <div v-if="confirmErrorMessage" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 mb-4">
          <p class="text-sm text-red-300">Could not start import.</p>
          <p class="text-xs text-red-200 mt-1">{{ confirmErrorMessage }}</p>
        </div>

        <div v-if="modalCanConfirm" class="space-y-3">
          <button
            v-for="mode in importModes"
            :key="mode.value"
            type="button"
            class="w-full rounded-lg border p-4 text-left transition-colors"
            :class="selectedImportMode === mode.value ? 'border-brand-500 bg-brand-500/10' : 'border-surface-200 bg-surface-100 hover:bg-surface-200'"
            @click="selectImportMode(mode.value)"
          >
            <p class="text-xs uppercase tracking-wide text-muted">{{ mode.tag }}</p>
            <p class="text-primary font-semibold mt-1">{{ mode.title }}</p>
            <p class="text-xs text-muted mt-1">{{ mode.description }}</p>
          </button>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button type="button" class="btn-ghost text-sm" @click="closeImportModal">Cancel</button>
          <button v-if="modalCanConfirm" type="button" class="btn-primary text-sm" :disabled="!modalJobId || confirmingImportMode" @click="confirmImportMode">
            {{ confirmingImportMode ? 'Starting import...' : 'Continue import' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { trackingAPI } from '@/api'
import { DATA_IMPORT_MODE, DATA_TRANSFER_FORMAT, DATA_TRANSFER_STATUS } from '@/constants/tracking'
import { formatDateTimeByLocale } from '@/i18n'
import { instantEpochMs, nowEpochMs } from '@/utils/temporal'

const zipInput = ref(null)
const yamtrackInput = ref(null)
const jsonInput = ref(null)
const jobs = ref([])
const zipError = ref('')
const yamtrackError = ref('')
const jsonError = ref('')
const showImportModeModal = ref(false)
const modalJobId = ref(null)
const selectedImportMode = ref(DATA_IMPORT_MODE.NEW_ITEMS)
const confirmingImportMode = ref(false)
const confirmErrorCode = ref('')

const confirmErrorMessages = {
  IMPORT_JOB_NOT_FOUND: 'This import job no longer exists. Please upload the file again.',
  IMPORT_CONFIRM_NOT_ALLOWED: 'This file type cannot be confirmed for import. Upload a valid file and try again.',
  IMPORT_NOT_READY: 'Import analysis is still running. Please wait a moment and try again.',
  IMPORT_MODE_INVALID: 'Please select a valid import mode and try again.',
}

const importModes = [
  {
    value: DATA_IMPORT_MODE.NEW_ITEMS,
    tag: 'Safe',
    title: 'Only bring new items',
    description: 'Adds import items that do not already exist. No updates and nothing removed.',
  },
  {
    value: DATA_IMPORT_MODE.UPDATE_EXISTING,
    tag: 'Recommended',
    title: 'Update when newer',
    description: 'Adds new items and refreshes existing matching items. Nothing is removed.',
  },
  {
    value: DATA_IMPORT_MODE.MIRROR_IMPORTED_SET,
    tag: 'Advanced',
    title: 'Mirror the imported set',
    description: 'Adds new items, updates existing ones, and removes missing items for imported collections.',
  },
]

const sevenDaysAgo = computed(() => nowEpochMs() - 7 * 24 * 60 * 60 * 1000)
const recentJobs = computed(() => {
  return jobs.value
    .filter((job) => job.job_type === 'import')
    .filter((job) => instantEpochMs(job.created_at) >= sevenDaysAgo.value)
    .sort((a, b) => instantEpochMs(b.created_at) - instantEpochMs(a.created_at))
})
const latestExport = computed(() => {
  return jobs.value
    .filter((job) => job.job_type === 'export')
    .sort((a, b) => instantEpochMs(b.created_at) - instantEpochMs(a.created_at))[0] || null
})
const modalSummary = computed(() => {
  const targetJob = jobs.value.find((item) => item.id === modalJobId.value)
  const summary = targetJob?.metadata?.summary || {}
  return {
    total: targetJob?.total_items || 0,
    history: summary.watch_history || 0,
    watchlist: summary.watchlist || 0,
    ratings: summary.ratings || 0,
  }
})
const modalJob = computed(() => jobs.value.find((item) => item.id === modalJobId.value) || null)
function progressTotal(job) {
  return job.total_items || 0
}
function stageLabel(job) {
  if (job.status !== 'processing') return ''
  const stage = job.metadata?.pipeline?.stage
  if (stage === 'finalizing') return 'Finalizing'
  return 'Importing'
}
const modalIsPreparing = computed(() => {
  if (!modalJob.value) return false
  return modalJob.value.status === DATA_TRANSFER_STATUS.PENDING || modalJob.value.status === DATA_TRANSFER_STATUS.PROCESSING
})
const modalCanConfirm = computed(() => modalJob.value?.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION)
const confirmErrorMessage = computed(() => {
  if (!confirmErrorCode.value) return ''
  return confirmErrorMessages[confirmErrorCode.value] || 'We could not start this import. Please try again.'
})

let timer = null

async function pollJob(jobId) {
  if (timer) clearInterval(timer)
  timer = setInterval(async () => {
    try {
      const status = await trackingAPI.getJobStatus(jobId)
      updateJob(status)
      if (
        status?.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION
        || status?.status === DATA_TRANSFER_STATUS.DONE
        || status?.status === DATA_TRANSFER_STATUS.FAILED
      ) {
        clearInterval(timer)
        timer = null
        await loadJobs()
      }
    } catch {
      clearInterval(timer)
      timer = null
    }
  }, 1500)
}

async function startZipImport() {
  zipError.value = ''
  confirmErrorCode.value = ''
  const file = zipInput.value?.files?.[0]
  if (!file) {
    zipError.value = 'Please choose a Trakt ZIP file before uploading.'
    return
  }
  if (!file.name.toLowerCase().endsWith('.zip')) {
    zipError.value = 'This import accepts ZIP files only.'
    return
  }
  const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.ZIP, 'trakt')
  updateJob(created)
  selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
  modalJobId.value = created.id
  showImportModeModal.value = true
  await pollJob(created.id)
}

async function startYamtrackImport() {
  yamtrackError.value = ''
  confirmErrorCode.value = ''
  const file = yamtrackInput.value?.files?.[0]
  if (!file) {
    yamtrackError.value = 'Please choose a Yamtrack CSV file before uploading.'
    return
  }
  if (!file.name.toLowerCase().endsWith('.csv')) {
    yamtrackError.value = 'This import accepts CSV files only.'
    return
  }
  const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.CSV, 'yamtrack')
  updateJob(created)
  selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
  modalJobId.value = created.id
  showImportModeModal.value = true
  await pollJob(created.id)
}

async function startJsonImport() {
  jsonError.value = ''
  confirmErrorCode.value = ''
  const file = jsonInput.value?.files?.[0]
  if (!file) {
    jsonError.value = 'Please choose an ArxMedia JSON backup before uploading.'
    return
  }
  if (!file.name.toLowerCase().endsWith('.json')) {
    jsonError.value = 'This import accepts JSON files only.'
    return
  }
  const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.JSON, 'arxmedia')
  updateJob(created)
  selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
  modalJobId.value = created.id
  showImportModeModal.value = true
  await pollJob(created.id)
}

function clearZipError() {
  zipError.value = ''
}

function clearYamtrackError() {
  yamtrackError.value = ''
}

function clearJsonError() {
  jsonError.value = ''
}

async function startExport() {
  const created = await trackingAPI.exportData(DATA_TRANSFER_FORMAT.JSON)
  updateJob(created)
  await pollJob(created.id)
}

function updateJob(updatedJob) {
  if (!updatedJob?.id) return
  const idx = jobs.value.findIndex((item) => item.id === updatedJob.id)
  if (idx >= 0) {
    jobs.value[idx] = updatedJob
  } else {
    jobs.value.unshift(updatedJob)
  }
}

function selectImportMode(mode) {
  selectedImportMode.value = mode
  confirmErrorCode.value = ''
}

async function loadJobs() {
  const data = await trackingAPI.listJobs()
  jobs.value = data.results || data || []
}

function latestProcessingJob() {
  return jobs.value
    .filter((job) => job?.status === DATA_TRANSFER_STATUS.PROCESSING)
    .sort((a, b) => instantEpochMs(b.created_at) - instantEpochMs(a.created_at))[0] || null
}

function humanStatus(value) {
  return String(value || '').replaceAll('_', ' ')
}

function statusClass(value) {
  if (value === DATA_TRANSFER_STATUS.DONE) return 'text-emerald-400'
  if (value === DATA_TRANSFER_STATUS.FAILED) return 'text-red-400'
  if (value === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION) return 'text-amber-400'
  return 'text-blue-400'
}

function formatDateTime(value) {
  return formatDateTimeByLocale(value)
}

async function confirmImportMode() {
  if (!modalJobId.value) return
  confirmingImportMode.value = true
  confirmErrorCode.value = ''
  try {
    const updated = await trackingAPI.confirmJobImport(modalJobId.value, selectedImportMode.value)
    updateJob(updated)
    showImportModeModal.value = false
    modalJobId.value = null
    await pollJob(updated.id)
  } catch (error) {
    confirmErrorCode.value = String(error?.error_code || '').trim() || 'UNKNOWN_CONFIRM_ERROR'
  } finally {
    confirmingImportMode.value = false
  }
}

function closeImportModal() {
  showImportModeModal.value = false
  confirmErrorCode.value = ''
  if (!modalCanConfirm.value) {
    modalJobId.value = null
  }
}

function openAwaitingJobModal(job) {
  if (!job || job.status !== DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION) return
  confirmErrorCode.value = ''
  modalJobId.value = job.id
  showImportModeModal.value = true
}

onMounted(async () => {
  await loadJobs()
  const processingJob = latestProcessingJob()
  if (processingJob?.id) {
    await pollJob(processingJob.id)
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
