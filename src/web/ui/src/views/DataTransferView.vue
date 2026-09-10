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

            <div class="space-y-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-surface-200 bg-surface px-3 py-2 text-sm transition-colors hover:border-brand-500/60 hover:bg-surface-200">
                <span class="min-w-0 flex-1 truncate font-medium text-primary">{{ zipFileName || 'Choose ZIP' }}</span>
                <span class="inline-flex items-center rounded-md bg-brand-500/15 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brand-300">Browse</span>
                <input
                  ref="zipInput"
                  type="file"
                  class="sr-only"
                  accept=".zip,application/zip"
                  aria-label="Import Trakt ZIP"
                  @change="handleZipFileSelect"
                />
              </label>
              <p class="text-xs text-muted">For Trakt export ZIP files only.</p>
              <p v-if="zipError" class="text-xs text-red-400">{{ zipError }}</p>
            </div>

            <div class="mt-3">
              <button type="button" class="btn-primary text-sm" :disabled="!zipFileName" @click="startZipImport">Upload ZIP</button>
            </div>
          </div>

          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">Import Yamtrack CSV</h3>
            </div>

            <div class="space-y-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-surface-200 bg-surface px-3 py-2 text-sm transition-colors hover:border-brand-500/60 hover:bg-surface-200">
                <span class="min-w-0 flex-1 truncate font-medium text-primary">{{ yamtrackFileName || 'Choose CSV' }}</span>
                <span class="inline-flex items-center rounded-md bg-brand-500/15 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brand-300">Browse</span>
                <input
                  ref="yamtrackInput"
                  type="file"
                  class="sr-only"
                  accept=".csv,text/csv"
                  aria-label="Import Yamtrack CSV"
                  @change="handleYamtrackFileSelect"
                />
              </label>
              <p class="text-xs text-muted">For Yamtrack CSV exports. Imports TMDB rows only.</p>
              <p v-if="yamtrackError" class="text-xs text-red-400">{{ yamtrackError }}</p>
            </div>

            <div class="mt-3">
              <button type="button" class="btn-primary text-sm" :disabled="!yamtrackFileName" @click="startYamtrackImport">Upload CSV</button>
            </div>
          </div>

          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">Import ArxMedia JSON</h3>
            </div>

            <div class="space-y-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-surface-200 bg-surface px-3 py-2 text-sm transition-colors hover:border-brand-500/60 hover:bg-surface-200">
                <span class="min-w-0 flex-1 truncate font-medium text-primary">{{ jsonFileName || 'Choose JSON' }}</span>
                <span class="inline-flex items-center rounded-md bg-brand-500/15 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brand-300">Browse</span>
                <input
                  ref="jsonInput"
                  type="file"
                  class="sr-only"
                  accept=".json,application/json"
                  aria-label="Import ArxMedia JSON"
                  @change="handleJsonFileSelect"
                />
              </label>
              <p class="text-xs text-muted">For JSON files exported from this app.</p>
              <p v-if="jsonError" class="text-xs text-red-400">{{ jsonError }}</p>
            </div>

            <div class="mt-3">
              <button type="button" class="btn-primary text-sm" :disabled="!jsonFileName" @click="startJsonImport">Upload JSON</button>
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
            :class="isJobDetailsOpenable(recentJob) ? 'cursor-pointer hover:bg-surface-200/70' : ''"
            @click="openJobModal(recentJob)"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm text-secondary">Started: <span class="text-primary">{{ formatDateTime(recentJob.created_at) }}</span></p>
              <span class="text-xs font-semibold uppercase tracking-wide" :class="statusClass(recentJob.status)">{{ humanStatus(recentJob.status) }}</span>
            </div>
            <p class="text-sm text-secondary mt-1">Progress: <span class="text-primary">{{ recentJob.processed_items }} / {{ progressTotal(recentJob) }}</span><span v-if="stageLabel(recentJob)" class="text-muted"> · {{ stageLabel(recentJob) }}</span></p>
            <p v-if="recentJob.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION" class="text-xs text-amber-400 mt-1">Click to pick import mode</p>
            <p v-else-if="isJobDetailsOpenable(recentJob)" class="text-xs text-muted mt-1">Click to view import details</p>
            <p v-if="recentJob.error_message" class="text-sm text-red-400 mt-1">{{ recentJob.error_message }}</p>
          </div>
        </div>
        <p v-else class="text-sm text-muted">No import jobs from the last 7 days.</p>
      </section>

      <section class="card p-5">
        <h2 class="text-primary font-semibold text-xl mb-1">Export File</h2>
        <p class="text-sm text-muted mb-4">Create a JSON backup export of your data.</p>
        <button type="button" class="btn-primary text-sm" @click="startExport">Create export</button>
        <p v-if="exportError" class="text-xs text-red-400 mt-2">{{ exportError }}</p>
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
       <div class="relative max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-xl border border-surface-200 bg-surface p-5 shadow-xl">
        <div class="flex items-start justify-between gap-4 mb-4">
          <div>
            <p class="text-xs uppercase tracking-wide text-muted">{{ modalIsFinished ? 'Import report' : 'Last step: pick a mode' }}</p>
            <h3 class="text-primary text-2xl font-display font-semibold">{{ modalIsFinished ? 'What happened?' : 'How should we import it?' }}</h3>
            <p class="text-sm text-muted mt-1">{{ modalIsFinished ? 'A record of what was imported and anything that needs attention.' : 'Choose how imported data interacts with what you already track here.' }}</p>
          </div>
           <button type="button" class="text-muted hover:text-primary" @click="closeImportModal">X</button>
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
            History: {{ modalSummary.history }} | Watchlist: {{ modalSummary.watchlist }} | Ratings: {{ modalSummary.ratings }} | Lists: {{ modalSummary.lists }}
          </p>
        </div>

        <div v-else-if="modalIsFinished" class="space-y-4">
          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-xs uppercase tracking-wide text-muted">Import result</p>
                <p class="text-primary text-xl font-semibold mt-1">{{ modalJob?.status === DATA_TRANSFER_STATUS.DONE ? 'Import finished' : 'Import did not finish' }}</p>
              </div>
              <span class="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide" :class="statusClass(modalJob?.status)">{{ humanStatus(modalJob?.status) }}</span>
            </div>
            <p class="text-sm text-secondary mt-3">{{ finishedResultSummary }}</p>
            <p class="text-xs text-muted mt-2">{{ humanValue(modalJob?.source) }} {{ (modalJob?.data_format || 'file').toUpperCase() }} import · {{ humanValue(modalJob?.import_mode) }}</p>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-6 gap-2">
            <div v-for="stat in finishedStats" :key="stat.label" class="rounded-lg border border-surface-200 bg-surface-100 p-3">
              <p class="text-xs text-muted">{{ stat.label }}</p>
              <p class="text-lg text-primary font-semibold mt-1">{{ stat.value }}</p>
            </div>
          </div>

          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <p class="text-xs uppercase tracking-wide text-muted">What was imported</p>
            <div class="mt-3 divide-y divide-surface-200">
              <div v-for="collection in finishedCollections" :key="collection.label" class="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <div>
                  <p class="text-sm text-primary">{{ collection.label }}</p>
                  <p class="text-xs text-muted">{{ collection.description }}</p>
                </div>
                  <p class="text-sm text-primary font-semibold whitespace-nowrap">{{ collection.found }} found</p>
                  <p v-if="collection.deleted" class="text-xs text-amber-300">{{ collection.deleted }} deleted</p>
              </div>
            </div>
          </div>

          <details v-if="finishedWarningDetails.length" class="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
            <summary class="cursor-pointer text-sm font-semibold text-amber-300">Warnings and skipped items ({{ finishedWarningDetails.length }})</summary>
            <div class="mt-3 space-y-3 border-t border-amber-500/30 pt-3">
              <div v-for="warning in finishedWarningDetails" :key="warning.key" class="text-xs">
                <div class="flex items-baseline justify-between gap-3">
                  <p class="font-medium text-amber-100">{{ warning.label }}</p>
                  <p class="shrink-0 font-semibold text-amber-300">{{ warning.value }}</p>
                </div>
                <p class="mt-1 text-amber-100/70">{{ warning.detail }}</p>
              </div>
            </div>
          </details>

          <div v-if="modalJob?.error_message" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3">
            <p class="text-sm font-semibold text-red-300">Job error</p>
            <p class="text-xs text-red-200 mt-1">{{ modalJob.error_message }}</p>
          </div>

          <details v-if="finishedFiles.length" class="rounded-lg border border-surface-200 bg-surface-100 p-3">
            <summary class="cursor-pointer text-sm font-medium text-secondary hover:text-primary">Technical file details ({{ finishedFiles.length }})</summary>
            <div class="mt-3 max-h-48 space-y-2 overflow-y-auto border-t border-surface-200 pt-3">
              <div v-for="file in finishedFiles" :key="file.file" class="flex items-start justify-between gap-3 text-sm">
                <span class="min-w-0 truncate text-primary">{{ file.file }}</span>
                <span class="shrink-0 text-right" :class="file.status === 'failed' ? 'text-red-300' : 'text-secondary'">{{ file.status === 'failed' ? file.error || 'Failed' : `${file.records_seen || 0} records` }}</span>
              </div>
            </div>
          </details>
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
          <button type="button" class="btn-ghost text-sm" @click="closeImportModal">Close</button>
          <button v-if="modalCanConfirm" type="button" class="btn-ghost text-sm border-red-500/40 text-red-300 hover:bg-red-500/10" :disabled="cancellingImport" @click="cancelImportJob">
            {{ cancellingImport ? 'Cancelling...' : 'Cancel' }}
          </button>
           <button v-if="modalCanConfirm" type="button" class="btn-primary text-sm" :disabled="!modalJobId || confirmingImportMode" @click="confirmImportMode">
            {{ confirmingImportMode ? 'Starting import...' : 'Continue import' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { trackingAPI } from '@/api'
import { DATA_IMPORT_MODE, DATA_TRANSFER_FORMAT, DATA_TRANSFER_STATUS } from '@/constants/tracking'
import { formatDateTimeByLocale } from '@/i18n'
import { instantEpochMs, nowEpochMs } from '@/utils/temporal'
import { getApiErrorMessage } from '@/utils/errors'
import type { DataTransferFileReport, DataTransferJob, DataTransferReport, DataTransferStatus, DataTransferWarning } from '@/types/api'

type ImportMode = (typeof DATA_IMPORT_MODE)[keyof typeof DATA_IMPORT_MODE]
type ImportModeOption = { value: ImportMode; tag: string; title: string; description: string }
type FinishedWarning = { key: string; label: string; value: string | number; detail: string }

const zipInput = ref<HTMLInputElement | null>(null)
const yamtrackInput = ref<HTMLInputElement | null>(null)
const jsonInput = ref<HTMLInputElement | null>(null)
const jobs = ref<DataTransferJob[]>([])
const zipError = ref('')
const yamtrackError = ref('')
const jsonError = ref('')
const zipFileName = ref('')
const yamtrackFileName = ref('')
const jsonFileName = ref('')
const zipFile = ref<File | null>(null)
const yamtrackFile = ref<File | null>(null)
const jsonFile = ref<File | null>(null)
const exportError = ref('')
const showImportModeModal = ref(false)
const modalJobId = ref<number | null>(null)
const selectedImportMode = ref<ImportMode>(DATA_IMPORT_MODE.NEW_ITEMS)
const confirmingImportMode = ref(false)
const cancellingImport = ref(false)
const confirmErrorCode = ref('')

const actionErrorMessages: Record<string, string> = {
  IMPORT_JOB_NOT_FOUND: 'This import job no longer exists. Please upload the file again.',
  IMPORT_CONFIRM_NOT_ALLOWED: 'This file type cannot be confirmed for import. Upload a valid file and try again.',
  IMPORT_NOT_READY: 'Import analysis is still running. Please wait a moment and try again.',
  IMPORT_MODE_INVALID: 'Please select a valid import mode and try again.',
  IMPORT_SOURCE_UNSUPPORTED: 'This import source is not supported.',
  IMPORT_SOURCE_FORMAT_MISMATCH: 'The import source and file format do not match.',
  IMPORT_INVALID_STATE_TRANSITION: 'This import is no longer in a state where that action can be performed.',
  IMPORT_CANCEL_NOT_ALLOWED: 'This import can no longer be cancelled.',
}

const importModes: ImportModeOption[] = [
  {
    value: DATA_IMPORT_MODE.NEW_ITEMS,
    tag: 'Safe',
    title: 'Only bring new items',
    description: 'Adds import items that do not already exist. No updates and nothing removed.',
  },
  {
    value: DATA_IMPORT_MODE.UPDATE_EXISTING,
    tag: 'Recommended',
    title: 'Import new items and update existing ones',
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
  const summary = targetJob?.metadata?.summary
  return {
    total: targetJob?.total_items || 0,
    history: summary?.watch_history || 0,
    watchlist: summary?.watchlist || 0,
    ratings: summary?.ratings || 0,
    lists: summary?.lists || 0,
  }
})
const modalJob = computed(() => jobs.value.find((item) => item.id === modalJobId.value) || null)
const modalIsFinished = computed(() => modalJob.value?.status === DATA_TRANSFER_STATUS.DONE || modalJob.value?.status === DATA_TRANSFER_STATUS.FAILED)
const finishedReport = computed<DataTransferReport>(() => modalJob.value?.metadata?.report || modalJob.value?.metadata || {})
const finishedResultSummary = computed(() => {
  if (modalJob.value?.status === DATA_TRANSFER_STATUS.FAILED) {
    return modalJob.value.error_message || 'The import could not be completed.'
  }
  const imported = Number(finishedReport.value.records_imported || 0)
  const skipped = Number(finishedReport.value.records_skipped || 0)
  const unchanged = Number(finishedReport.value.records_unchanged || 0)
  const deleted = Number(finishedReport.value.deleted_total || 0)
  const lists = Number(finishedReport.value.lists_imported || 0)
  const listItems = Number(finishedReport.value.list_items_imported || 0)
  const parts: string[] = []
  if (imported) parts.push(`${imported} records imported`)
  if (deleted) parts.push(`${deleted} existing records deleted to mirror the import`)
  if (skipped) parts.push(`${skipped} records skipped`)
  if (unchanged) parts.push(`${unchanged} records already matched`)
  if (lists) parts.push(`${lists} lists imported`)
  if (listItems) parts.push(`${listItems} list items imported`)
  return parts.length ? `${parts.join('. ')}.` : 'The import completed without any records to add.'
})
const finishedStats = computed(() => [
  { label: 'Total records', value: finishedReport.value.records_seen ?? modalJob.value?.total_items ?? 0 },
  { label: 'Imported', value: finishedReport.value.records_imported ?? 0 },
  { label: 'Skipped', value: finishedReport.value.records_skipped ?? 0 },
  { label: 'Already matched', value: finishedReport.value.records_unchanged ?? 0 },
  { label: 'Deleted', value: finishedReport.value.deleted_total ?? 0 },
  { label: 'Metadata errors', value: finishedReport.value.metadata_errors ?? 0 },
])
const finishedCollections = computed(() => {
  const summary = finishedReport.value.summary
  const deleted = finishedReport.value.deleted
  return [
    {
      label: 'Watch history',
      description: 'Movies and episodes marked watched',
      found: Number(summary?.watch_history || 0),
      deleted: Number(deleted?.watch_history || 0),
    },
    {
      label: 'Watchlist',
      description: 'Movies and shows saved to watch later',
      found: Number(summary?.watchlist || 0),
      deleted: Number(deleted?.watchlist || 0),
    },
    {
      label: 'Ratings',
      description: 'Ratings included in the import',
      found: Number(summary?.ratings || 0),
      deleted: Number(deleted?.ratings || 0),
    },
    {
      label: 'Lists',
      description: 'Custom lists restored from the import',
      found: Number(summary?.lists || 0),
      deleted: Number(deleted?.lists || 0),
    },
  ]
})
const finishedFiles = computed<DataTransferFileReport[]>(() => Array.isArray(finishedReport.value.files) ? finishedReport.value.files : [])
const finishedWarningDetails = computed(() => {
  const report = finishedReport.value
  const warnings: FinishedWarning[] = []
  if (Array.isArray(report.warnings)) {
    report.warnings.forEach((warning, index) => warnings.push({
      key: `${warning.code || 'warning'}-${index}`,
      label: humanWarningCode(warning.code),
      value: formatWarningLocation(warning.location),
      detail: warning.message || 'This item could not be imported.',
    }))
  }
  const warningDefinitions: Record<string, Omit<FinishedWarning, 'key' | 'value'>> = {
    invalid_count: {
      label: 'Invalid records',
      detail: 'Rows could not be parsed or did not contain enough valid data to import.',
    },
    unsupported_files: {
      label: 'Unsupported files',
      detail: 'Files in the export were recognized but are not part of the supported import collections.',
    },
    unsupported_records: {
      label: 'Unsupported records',
      detail: 'Records belonged to an unsupported type or export section and were not imported.',
    },
    skipped_non_tmdb: {
      label: 'Non-TMDB rows skipped',
      detail: 'Only rows linked to TMDB media can be imported. Other providers were left out.',
    },
    skipped_unsupported_media_type: {
      label: 'Unsupported media types skipped',
      detail: 'The row used a media type that this import does not support.',
    },
    skipped_invalid_status: {
      label: 'Invalid statuses skipped',
      detail: 'The row contained a status that could not be mapped to an ArxMedia status.',
    },
    skipped_missing_tmdb_id: {
      label: 'Rows missing a TMDB ID',
      detail: 'The row did not include a TMDB ID, so it could not be matched to media.',
    },
    files_failed: {
      label: 'Files failed',
      detail: 'One or more files could not be read. See the failed file names below.',
    },
    metadata_errors: {
      label: 'Metadata lookups failed',
      detail: 'Tracking data was retained, but some movie or show metadata could not be refreshed.',
    },
  }
  Object.entries(warningDefinitions).forEach(([key, definition]) => {
    if (Number(report[key] || 0) > 0) warnings.push({
      key: `aggregate-${key}`,
      label: definition.label,
      value: String(report[key]),
      detail: definition.detail,
    })
  })
  const failedFiles = finishedFiles.value.filter((file) => file.status === 'failed')
  failedFiles.forEach((file) => warnings.push({
    key: `file-${file.file}`,
    label: file.file,
    value: 'Failed',
    detail: file.error || 'The file could not be processed.',
  }))
  return warnings
})

function humanWarningCode(code: string | undefined) {
  const title = String(code || 'warning').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  return title.replace('Tmdb', 'TMDB')
}

function formatWarningLocation(location: DataTransferWarning['location'] = {}) {
  if (location.kind === 'csv_row') return `${location.file || 'CSV file'}, row ${location.row}${location.column ? `, column ${location.column}` : ''}`
  if (location.kind === 'zip_record') return `${location.file || 'ZIP entry'}, record ${location.record}`
  if (location.kind === 'zip_file') return `${location.file || 'ZIP entry'}`
  if (location.kind === 'json_item') return `${location.collection || 'JSON collection'}, item ${location.index}${location.field ? `, field ${location.field}` : ''}`
  return 'Location not available'
}
function progressTotal(job: DataTransferJob) {
  return job.total_items || 0
}
function stageLabel(job: DataTransferJob) {
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
  return actionErrorMessages[confirmErrorCode.value] || 'The requested import action could not be completed.'
})

let timer: ReturnType<typeof setInterval> | null = null

async function pollJob(jobId: number) {
  if (timer !== null) clearInterval(timer)
  timer = setInterval(async () => {
    try {
      const status = await trackingAPI.getJobStatus(jobId)
      updateJob(status)
      if (
        status?.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION
        || status?.status === DATA_TRANSFER_STATUS.DONE
        || status?.status === DATA_TRANSFER_STATUS.FAILED
      ) {
        if (timer !== null) clearInterval(timer)
        timer = null
        await loadJobs()
      }
    } catch {
      if (timer !== null) clearInterval(timer)
      timer = null
    }
  }, 1500)
}

function handleZipFileSelect(event: Event) {
  zipError.value = ''
  zipFile.value = selectedFile(event)
  zipFileName.value = zipFile.value?.name || ''
}

function handleYamtrackFileSelect(event: Event) {
  yamtrackError.value = ''
  yamtrackFile.value = selectedFile(event)
  yamtrackFileName.value = yamtrackFile.value?.name || ''
}

function handleJsonFileSelect(event: Event) {
  jsonError.value = ''
  jsonFile.value = selectedFile(event)
  jsonFileName.value = jsonFile.value?.name || ''
}

function selectedFile(event: Event): File | null {
  const input = event.currentTarget as HTMLInputElement | null
  return input?.files?.[0] || null
}

async function startZipImport() {
  zipError.value = ''
  confirmErrorCode.value = ''
  const file = zipFile.value
  if (!file) {
    zipError.value = 'Please choose a Trakt ZIP file before uploading.'
    zipFileName.value = ''
    return
  }
  if (!file.name.toLowerCase().endsWith('.zip')) {
    zipError.value = 'This import accepts ZIP files only.'
    return
  }
  try {
    const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.ZIP, 'trakt')
    updateJob(created)
    selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
    modalJobId.value = created.id
    showImportModeModal.value = true
    await pollJob(created.id)
  } catch (error) {
    zipError.value = getApiErrorMessage(error, 'The ZIP import could not be started.')
  }
}

async function startYamtrackImport() {
  yamtrackError.value = ''
  confirmErrorCode.value = ''
  const file = yamtrackFile.value
  if (!file) {
    yamtrackError.value = 'Please choose a Yamtrack CSV file before uploading.'
    yamtrackFileName.value = ''
    return
  }
  if (!file.name.toLowerCase().endsWith('.csv')) {
    yamtrackError.value = 'This import accepts CSV files only.'
    return
  }
  try {
    const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.CSV, 'yamtrack')
    updateJob(created)
    selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
    modalJobId.value = created.id
    showImportModeModal.value = true
    await pollJob(created.id)
  } catch (error) {
    yamtrackError.value = getApiErrorMessage(error, 'The CSV import could not be started.')
  }
}

async function startJsonImport() {
  jsonError.value = ''
  confirmErrorCode.value = ''
  const file = jsonFile.value
  if (!file) {
    jsonError.value = 'Please choose an ArxMedia JSON backup before uploading.'
    jsonFileName.value = ''
    return
  }
  if (!file.name.toLowerCase().endsWith('.json')) {
    jsonError.value = 'This import accepts JSON files only.'
    return
  }
  try {
    const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.JSON, 'arxmedia')
    updateJob(created)
    selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
    modalJobId.value = created.id
    showImportModeModal.value = true
    await pollJob(created.id)
  } catch (error) {
    jsonError.value = getApiErrorMessage(error, 'The JSON import could not be started.')
  }
}

async function startExport() {
  exportError.value = ''
  try {
    const created = await trackingAPI.exportData(DATA_TRANSFER_FORMAT.JSON)
    updateJob(created)
    await pollJob(created.id)
  } catch (error) {
    exportError.value = getApiErrorMessage(error, 'The export could not be started.')
  }
}

function updateJob(updatedJob: DataTransferJob | null | undefined) {
  if (!updatedJob?.id) return
  const idx = jobs.value.findIndex((item) => item.id === updatedJob.id)
  if (idx >= 0) {
    jobs.value[idx] = updatedJob
  } else {
    jobs.value.unshift(updatedJob)
  }
}

function selectImportMode(mode: ImportMode) {
  selectedImportMode.value = mode
  confirmErrorCode.value = ''
}

async function loadJobs() {
  const data = await trackingAPI.listJobs()
  jobs.value = Array.isArray(data) ? data : data.results || []
}

function latestProcessingJob() {
  return jobs.value
    .filter((job) => job?.status === DATA_TRANSFER_STATUS.PROCESSING)
    .sort((a, b) => instantEpochMs(b.created_at) - instantEpochMs(a.created_at))[0] || null
}

function humanStatus(value: DataTransferStatus | undefined) {
  return String(value || '').replaceAll('_', ' ')
}

function humanValue(value: string | undefined) {
  return String(value || 'unknown').replaceAll('_', ' ')
}

function isJobDetailsOpenable(job: DataTransferJob) {
  return job.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION || job.status === DATA_TRANSFER_STATUS.DONE || job.status === DATA_TRANSFER_STATUS.FAILED
}

function statusClass(value: DataTransferStatus | undefined) {
  if (value === DATA_TRANSFER_STATUS.DONE) return 'text-emerald-400'
  if (value === DATA_TRANSFER_STATUS.FAILED || value === DATA_TRANSFER_STATUS.CANCELLED) return 'text-red-400'
  if (value === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION) return 'text-amber-400'
  return 'text-blue-400'
}

function formatDateTime(value: string) {
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
    confirmErrorCode.value = getErrorCode(error) || 'UNKNOWN_CONFIRM_ERROR'
  } finally {
    confirmingImportMode.value = false
  }
}

async function cancelImportJob() {
  if (!modalJobId.value || cancellingImport.value) return
  cancellingImport.value = true
  confirmErrorCode.value = ''
  try {
    const updated = await trackingAPI.cancelJobImport(modalJobId.value)
    updateJob(updated)
    showImportModeModal.value = false
    modalJobId.value = null
  } catch (error) {
    confirmErrorCode.value = getErrorCode(error) || 'UNKNOWN_CANCEL_ERROR'
  } finally {
    cancellingImport.value = false
  }
}

function closeImportModal() {
  showImportModeModal.value = false
  confirmErrorCode.value = ''
  if (!modalCanConfirm.value) {
    modalJobId.value = null
  }
}

function getErrorCode(error: unknown): string {
  return typeof error === 'object' && error !== null && 'error_code' in error && typeof error.error_code === 'string'
    ? error.error_code.trim()
    : ''
}

function openJobModal(job: DataTransferJob) {
  if (!isJobDetailsOpenable(job)) return
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
  if (timer !== null) clearInterval(timer)
})
</script>
