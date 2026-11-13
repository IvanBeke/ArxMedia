<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <header class="mb-6">
      <h1 class="font-display text-3xl text-primary font-semibold tracking-tight">{{ t('page_import_data') }}</h1>
      <p class="text-sm text-muted mt-1">{{ t('data_transfer_intro') }}</p>
    </header>

    <div class="space-y-6">
      <section class="card p-5">
        <h2 class="text-primary font-semibold text-xl mb-1">{{ t('page_import_data') }}</h2>
        <p class="text-sm text-muted mb-4">{{ t('data_transfer_import_hint') }}</p>
        <div class="grid md:grid-cols-2 gap-3">
          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">{{ t('data_transfer_import_trakt_zip') }}</h3>
            </div>

            <div class="space-y-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-surface-200 bg-surface px-3 py-2 text-sm transition-colors hover:border-brand-500/60 hover:bg-surface-200">
                <span class="min-w-0 flex-1 truncate font-medium text-primary">{{ zipFileName || t('data_transfer_choose_zip') }}</span>
                <span class="inline-flex items-center rounded-md bg-brand-500/15 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brand-300">{{ t('data_transfer_browse') }}</span>
                <input
                  ref="zipInput"
                  type="file"
                  class="sr-only"
                  accept=".zip,application/zip"
                  :aria-label="t('data_transfer_import_trakt_zip')"
                  @change="handleZipFileSelect"
                />
              </label>
              <p class="text-xs text-muted">{{ t('data_transfer_trakt_hint') }}</p>
              <p v-if="zipError" class="text-xs text-red-400">{{ zipError }}</p>
            </div>

            <div class="mt-3">
              <button type="button" class="btn-primary text-sm" :disabled="!zipFileName" @click="startZipImport">{{ t('data_transfer_upload_zip') }}</button>
            </div>
          </div>

          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">{{ t('data_transfer_import_wetrakr_zip') }}</h3>
            </div>

            <div class="space-y-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-surface-200 bg-surface px-3 py-2 text-sm transition-colors hover:border-brand-500/60 hover:bg-surface-200">
                <span class="min-w-0 flex-1 truncate font-medium text-primary">{{ wetrakrFileName || t('data_transfer_choose_zip') }}</span>
                <span class="inline-flex items-center rounded-md bg-brand-500/15 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brand-300">{{ t('data_transfer_browse') }}</span>
                <input
                  ref="wetrakrInput"
                  type="file"
                  class="sr-only"
                  accept=".zip,application/zip"
                  :aria-label="t('data_transfer_import_wetrakr_zip')"
                  @change="handleWetrakrFileSelect"
                />
              </label>
              <p class="text-xs text-muted">{{ t('data_transfer_wetrakr_hint') }}</p>
              <p v-if="wetrakrError" class="text-xs text-red-400">{{ wetrakrError }}</p>
            </div>

            <div class="mt-3">
              <button type="button" class="btn-primary text-sm" :disabled="!wetrakrFileName" @click="startWetrakrImport">{{ t('data_transfer_upload_zip') }}</button>
            </div>
          </div>

          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">{{ t('data_transfer_import_yamtrack_csv') }}</h3>
            </div>

            <div class="space-y-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-surface-200 bg-surface px-3 py-2 text-sm transition-colors hover:border-brand-500/60 hover:bg-surface-200">
                <span class="min-w-0 flex-1 truncate font-medium text-primary">{{ yamtrackFileName || t('data_transfer_choose_csv') }}</span>
                <span class="inline-flex items-center rounded-md bg-brand-500/15 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brand-300">{{ t('data_transfer_browse') }}</span>
                <input
                  ref="yamtrackInput"
                  type="file"
                  class="sr-only"
                  accept=".csv,text/csv"
                  :aria-label="t('data_transfer_import_yamtrack_csv')"
                  @change="handleYamtrackFileSelect"
                />
              </label>
              <p class="text-xs text-muted">{{ t('data_transfer_yamtrack_hint') }}</p>
              <p v-if="yamtrackError" class="text-xs text-red-400">{{ yamtrackError }}</p>
            </div>

            <div class="mt-3">
              <button type="button" class="btn-primary text-sm" :disabled="!yamtrackFileName" @click="startYamtrackImport">{{ t('data_transfer_upload_csv') }}</button>
            </div>
          </div>

          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-2 mb-2">
              <h3 class="text-primary font-medium">{{ t('data_transfer_import_arxmedia_backup') }}</h3>
            </div>

            <div class="space-y-2">
              <label class="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-surface-200 bg-surface px-3 py-2 text-sm transition-colors hover:border-brand-500/60 hover:bg-surface-200">
                <span class="min-w-0 flex-1 truncate font-medium text-primary">{{ arxmediaFileName || t('data_transfer_choose_zip') }}</span>
                <span class="inline-flex items-center rounded-md bg-brand-500/15 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brand-300">{{ t('data_transfer_browse') }}</span>
                <input
                  ref="arxmediaInput"
                  type="file"
                  class="sr-only"
                  accept=".zip,application/zip"
                  :aria-label="t('data_transfer_import_arxmedia_backup_label')"
                  @change="handleArxmediaFileSelect"
                />
              </label>
              <p class="text-xs text-muted">{{ t('data_transfer_arxmedia_hint') }}</p>
              <p v-if="arxmediaError" class="text-xs text-red-400">{{ arxmediaError }}</p>
            </div>

            <div class="mt-3">
              <button type="button" class="btn-primary text-sm" :disabled="!arxmediaFileName" @click="startArxmediaImport">{{ t('data_transfer_upload_backup') }}</button>
            </div>
          </div>
        </div>
      </section>

      <section class="card p-5">
        <h2 class="text-primary font-semibold text-xl mb-3">{{ t('data_transfer_recent_jobs') }}</h2>
        <p v-if="pollError" role="alert" class="text-xs text-amber-400 mb-2">{{ pollError }}</p>
        <div v-if="recentJobs.length" class="space-y-3">
          <div
            v-for="recentJob in recentJobs"
            :key="recentJob.id"
            class="rounded-lg border border-surface-200 bg-surface-100 p-3"
            :class="isJobDetailsOpenable(recentJob) ? 'cursor-pointer hover:bg-surface-200/70' : ''"
            @click="openJobModal(recentJob)"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm text-secondary">{{ t('data_transfer_started') }} <span class="text-primary">{{ formatDateTimeByLocale(recentJob.created_at) }}</span></p>
              <span class="text-xs font-semibold uppercase tracking-wide" :class="statusClass(recentJob.status)">{{ humanStatus(recentJob.status) }}</span>
            </div>
            <p class="text-sm text-secondary mt-1">{{ t('data_transfer_progress') }} <span class="text-primary">{{ recentJob.processed_items }} / {{ progressTotal(recentJob) }}</span><span v-if="stageLabel(recentJob)" class="text-muted"> · {{ stageLabel(recentJob) }}</span></p>
            <p v-if="recentJob.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION" class="text-xs text-amber-400 mt-1">{{ t('data_transfer_click_pick_mode') }}</p>
            <p v-else-if="isJobDetailsOpenable(recentJob)" class="text-xs text-muted mt-1">{{ t('data_transfer_click_view_details') }}</p>
            <p v-if="recentJob.error_message" class="text-sm text-red-400 mt-1">{{ recentJob.error_message }}</p>
          </div>
        </div>
        <p v-else class="text-sm text-muted">{{ t('data_transfer_no_recent_jobs') }}</p>
      </section>

      <section class="card p-5">
        <h2 class="text-primary font-semibold text-xl mb-1">{{ t('data_transfer_export_title') }}</h2>
        <p class="text-sm text-muted mb-4">{{ t('data_transfer_export_hint') }}</p>
        <div class="flex items-center gap-3">
          <button type="button" class="btn-primary text-sm" @click="startExport">{{ t('data_transfer_create_export') }}</button>
          <a
            v-if="latestExport?.output_url"
            :href="latestExport.output_url"
            download
            class="btn-primary text-sm"
          >
            {{ t('data_transfer_download_export') }}
          </a>
          <button v-else type="button" class="btn-primary text-sm" disabled>
            {{ exportRunning ? t('data_transfer_generating') : t('data_transfer_no_export_yet') }}
          </button>
        </div>
        <p v-if="exportError" class="text-xs text-red-400 mt-2">{{ exportError }}</p>
        <div v-if="recentExports.length" class="mt-4 space-y-2">
          <p class="text-xs uppercase tracking-wide text-muted">{{ t('data_transfer_recent_exports') }}</p>
          <div
            v-for="exportJob in recentExports"
            :key="exportJob.id"
            class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-surface-200 bg-surface-100 p-3"
          >
            <div class="min-w-0">
              <p class="text-sm text-secondary">{{ t('data_transfer_created') }} <span class="text-primary">{{ formatDateTimeByLocale(exportJob.created_at) }}</span></p>
              <p class="text-xs text-muted mt-0.5">
                <span class="font-semibold uppercase tracking-wide" :class="exportStatusById[exportJob.id]?.className">{{ exportStatusById[exportJob.id]?.text }}</span>
                <span v-if="exportJob.output_url"> · <a :href="exportJob.output_url" download class="text-brand-400 hover:text-brand-300">{{ exportJob.output_filename }}</a></span>
              </p>
            </div>
            <button
              v-if="exportJob.output_url"
              type="button"
              class="btn-ghost text-xs border-red-500/40 text-red-300 hover:bg-red-500/10"
              :disabled="deletingExportId === exportJob.id"
              @click="askDeleteExport(exportJob.id)"
            >
              {{ deletingExportId === exportJob.id ? t('data_transfer_deleting') : t('data_transfer_delete_file') }}
            </button>
          </div>
        </div>
        <p v-else class="text-sm text-muted mt-4">{{ t('data_transfer_no_exports') }}</p>
        <ConfirmDialog
          ref="deleteExportDialog"
          :title="t('data_transfer_delete_export_title')"
          :message="t('data_transfer_delete_export_message')"
          :confirm-label="t('data_transfer_delete_file')"
          :loading-label="t('data_transfer_deleting')"
          :loading="deletingExportId !== null"
          @confirm="confirmDeleteExport"
        />
      </section>
    </div>

    <div v-if="showImportModeModal" class="fixed inset-0 z-[150] flex items-center justify-center p-4">
      <button
        type="button"
        class="absolute inset-0 bg-black/60"
        :aria-label="t('data_transfer_modal_close_label')"
        @click="closeImportModal"
      ></button>
       <div class="relative max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-xl border border-surface-200 bg-surface p-5 shadow-xl">
        <div class="flex items-start justify-between gap-4 mb-4">
          <div>
            <p class="text-xs uppercase tracking-wide text-muted">{{ modalIsFinished ? t('data_transfer_report_tag') : t('data_transfer_step_tag') }}</p>
            <h3 class="text-primary text-2xl font-display font-semibold">{{ modalIsFinished ? t('data_transfer_what_happened') : t('data_transfer_how_import') }}</h3>
            <p class="text-sm text-muted mt-1">{{ modalIsFinished ? t('data_transfer_report_desc') : t('data_transfer_mode_desc') }}</p>
          </div>
           <button type="button" class="text-muted hover:text-primary" @click="closeImportModal">X</button>
        </div>

        <div v-if="modalIsPreparing" class="rounded-lg border border-surface-200 bg-surface-100 p-6 mb-4 text-center">
          <div class="inline-block h-8 w-8 animate-spin rounded-full border-2 border-surface-300 border-t-brand-500"></div>
          <p class="text-primary font-semibold mt-3">{{ t('data_transfer_preparing') }}</p>
          <p class="text-sm text-muted mt-1">{{ t('data_transfer_preparing_desc') }}</p>
        </div>

        <div v-else-if="modalCanConfirm" class="rounded-lg border border-surface-200 bg-surface-100 p-3 mb-4">
          <p class="text-sm text-secondary">{{ t('data_transfer_items_found') }}</p>
          <p class="text-lg text-primary font-semibold">{{ modalSummary.total }}</p>
          <p class="text-xs text-muted mt-1">
            {{ t('data_transfer_summary_breakdown', modalSummary) }}
          </p>
        </div>

        <div v-else-if="modalIsFinished" class="space-y-4">
          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-xs uppercase tracking-wide text-muted">{{ t('data_transfer_import_result') }}</p>
                <p class="text-primary text-xl font-semibold mt-1">{{ modalJob?.status === DATA_TRANSFER_STATUS.DONE ? t('data_transfer_import_finished') : t('data_transfer_import_not_finished') }}</p>
              </div>
              <span class="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide" :class="statusClass(modalJob?.status)">{{ humanStatus(modalJob?.status) }}</span>
            </div>
            <p class="text-sm text-secondary mt-3">{{ finishedResultSummary }}</p>
            <p class="text-xs text-muted mt-2">{{ t('data_transfer_import_summary', { source: humanValue(modalJob?.source), format: (modalJob?.data_format || t('data_transfer_file')).toUpperCase(), mode: humanValue(modalJob?.import_mode) }) }}</p>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-6 gap-2">
            <div v-for="stat in finishedStats" :key="stat.label" class="rounded-lg border border-surface-200 bg-surface-100 p-3">
              <p class="text-xs text-muted">{{ stat.label }}</p>
              <p class="text-lg text-primary font-semibold mt-1">{{ stat.value }}</p>
            </div>
          </div>

          <div class="rounded-lg border border-surface-200 bg-surface-100 p-4">
            <p class="text-xs uppercase tracking-wide text-muted">{{ t('data_transfer_what_imported') }}</p>
            <div class="mt-3 divide-y divide-surface-200">
              <div v-for="collection in finishedCollections" :key="collection.label" class="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <div>
                  <p class="text-sm text-primary">{{ collection.label }}</p>
                  <p class="text-xs text-muted">{{ collection.description }}</p>
                </div>
                  <p class="text-sm text-primary font-semibold whitespace-nowrap">{{ t('data_transfer_found', { count: collection.found }) }}</p>
                  <p v-if="collection.deleted" class="text-xs text-amber-300">{{ t('data_transfer_deleted_count', { count: collection.deleted }) }}</p>
              </div>
            </div>
            <details v-if="finishedListDetails.length" class="mt-3 rounded-lg border border-surface-200 bg-surface p-3">
              <summary class="cursor-pointer text-sm font-medium text-secondary hover:text-primary">{{ t('data_transfer_lists_in_detail', { count: finishedListDetails.length }) }}</summary>
              <div class="mt-3 space-y-3 border-t border-surface-200 pt-3">
                <div v-for="list in finishedListDetails" :key="list.name">
                  <div class="flex items-baseline justify-between gap-3">
                    <p class="text-sm font-medium text-primary">{{ list.name }}</p>
                    <p class="shrink-0 text-xs text-muted">{{ t('list_item_count', { count: list.items.length }) }}{{ list.privacy ? ` · ${list.privacy}` : '' }}</p>
                  </div>
                  <ul class="mt-1 space-y-1">
                    <li v-for="item in list.items" :key="`${item.media_type}-${item.tmdb_id}`" class="flex items-baseline justify-between gap-3 text-xs">
                      <span class="min-w-0 truncate text-secondary">{{ item.title || `TMDB ${item.tmdb_id}` }}</span>
                      <span class="shrink-0 text-muted">{{ item.media_type }}</span>
                    </li>
                  </ul>
                </div>
              </div>
            </details>
          </div>

          <details v-if="finishedWarningDetails.length" class="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
            <summary class="cursor-pointer text-sm font-semibold text-amber-300">{{ t('data_transfer_warnings_title', { count: finishedWarningDetails.length }) }}</summary>
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
            <p class="text-sm font-semibold text-red-300">{{ t('data_transfer_job_error') }}</p>
            <p class="text-xs text-red-200 mt-1">{{ modalJob.error_message }}</p>
          </div>

          <details v-if="finishedFiles.length" class="rounded-lg border border-surface-200 bg-surface-100 p-3">
            <summary class="cursor-pointer text-sm font-medium text-secondary hover:text-primary">{{ t('data_transfer_file_details', { count: finishedFiles.length }) }}</summary>
            <div class="mt-3 max-h-48 space-y-2 overflow-y-auto border-t border-surface-200 pt-3">
              <div v-for="file in finishedFiles" :key="file.file" class="flex items-start justify-between gap-3 text-sm">
                <span class="min-w-0 truncate text-primary">{{ file.file }}</span>
                <span class="shrink-0 text-right" :class="file.status === 'failed' ? 'text-red-300' : 'text-secondary'">{{ file.status === 'failed' ? file.error || t('data_transfer_failed') : t('data_transfer_records_count', { count: file.records_seen || 0 }) }}</span>
              </div>
            </div>
          </details>
        </div>

        <div v-if="confirmErrorMessage" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 mb-4">
          <p class="text-sm text-red-300">{{ t('data_transfer_start_failed') }}</p>
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
          <button type="button" class="btn-ghost text-sm" @click="closeImportModal">{{ t('common_close') }}</button>
          <button v-if="modalCanConfirm" type="button" class="btn-ghost text-sm border-red-500/40 text-red-300 hover:bg-red-500/10" :disabled="cancellingImport" @click="cancelImportJob">
            {{ cancellingImport ? t('data_transfer_cancelling') : t('common_cancel') }}
          </button>
           <button v-if="modalCanConfirm" type="button" class="btn-primary text-sm" :disabled="!modalJobId || confirmingImportMode" @click="confirmImportMode">
            {{ confirmingImportMode ? t('data_transfer_starting') : t('data_transfer_continue') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { trackingAPI } from '@/api'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { DATA_IMPORT_MODE, DATA_TRANSFER_FORMAT, DATA_TRANSFER_STATUS } from '@/constants/tracking'
import { formatDateTimeByLocale, useI18n, type MessageKey } from '@/i18n'
import { usePageTitle } from '@/composables/usePageTitle'
import { instantEpochMs, nowEpochMs } from '@/utils/temporal'
import { getApiErrorMessage } from '@/utils/errors'
import type { DataTransferFileReport, DataTransferJob, DataTransferListDetail, DataTransferReport, DataTransferStatus, DataTransferWarning } from '@/types/api'

const { t } = useI18n()
usePageTitle(() => t('page_import_data'))

type ImportMode = (typeof DATA_IMPORT_MODE)[keyof typeof DATA_IMPORT_MODE]
type ImportModeOption = { value: ImportMode; tag: string; title: string; description: string }
type FinishedWarning = { key: string; label: string; value: string | number; detail: string }

const zipInput = ref<HTMLInputElement | null>(null)
const wetrakrInput = ref<HTMLInputElement | null>(null)
const yamtrackInput = ref<HTMLInputElement | null>(null)
const arxmediaInput = ref<HTMLInputElement | null>(null)
const jobs = ref<DataTransferJob[]>([])
const zipError = ref('')
const wetrakrError = ref('')
const yamtrackError = ref('')
const arxmediaError = ref('')
const zipFileName = ref('')
const wetrakrFileName = ref('')
const yamtrackFileName = ref('')
const arxmediaFileName = ref('')
const zipFile = ref<File | null>(null)
const wetrakrFile = ref<File | null>(null)
const yamtrackFile = ref<File | null>(null)
const arxmediaFile = ref<File | null>(null)
const exportError = ref('')
const showImportModeModal = ref(false)
const modalJobId = ref<number | null>(null)
const selectedImportMode = ref<ImportMode>(DATA_IMPORT_MODE.NEW_ITEMS)
const confirmingImportMode = ref(false)
const cancellingImport = ref(false)
const confirmErrorCode = ref('')

const actionErrorKeys: Record<string, MessageKey> = {
  IMPORT_JOB_NOT_FOUND: 'data_transfer_error_job_not_found',
  IMPORT_CONFIRM_NOT_ALLOWED: 'data_transfer_error_confirm_not_allowed',
  IMPORT_NOT_READY: 'data_transfer_error_not_ready',
  IMPORT_MODE_INVALID: 'data_transfer_error_mode_invalid',
  IMPORT_SOURCE_UNSUPPORTED: 'data_transfer_error_source_unsupported',
  IMPORT_SOURCE_FORMAT_MISMATCH: 'data_transfer_error_format_mismatch',
  IMPORT_INVALID_STATE_TRANSITION: 'data_transfer_error_invalid_state',
  IMPORT_CANCEL_NOT_ALLOWED: 'data_transfer_error_cancel_not_allowed',
}

const importModes = computed<ImportModeOption[]>(() => [
  {
    value: DATA_IMPORT_MODE.NEW_ITEMS,
    tag: t('data_transfer_mode_safe_tag'),
    title: t('data_transfer_mode_new_items_title'),
    description: t('data_transfer_mode_new_items_desc'),
  },
  {
    value: DATA_IMPORT_MODE.UPDATE_EXISTING,
    tag: t('data_transfer_mode_recommended_tag'),
    title: t('data_transfer_mode_update_existing_title'),
    description: t('data_transfer_mode_update_existing_desc'),
  },
  {
    value: DATA_IMPORT_MODE.MIRROR_IMPORTED_SET,
    tag: t('data_transfer_mode_advanced_tag'),
    title: t('data_transfer_mode_mirror_title'),
    description: t('data_transfer_mode_mirror_desc'),
  },
])

const statusKeys: Record<string, MessageKey> = {
  [DATA_TRANSFER_STATUS.PENDING]: 'data_transfer_status_pending',
  [DATA_TRANSFER_STATUS.PROCESSING]: 'data_transfer_status_processing',
  [DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION]: 'data_transfer_status_awaiting_confirmation',
  [DATA_TRANSFER_STATUS.DONE]: 'data_transfer_status_done',
  [DATA_TRANSFER_STATUS.FAILED]: 'data_transfer_status_failed',
  [DATA_TRANSFER_STATUS.CANCELLED]: 'data_transfer_status_cancelled',
}

const importModeValueKeys: Record<string, MessageKey> = {
  [DATA_IMPORT_MODE.NEW_ITEMS]: 'data_transfer_mode_value_new_items',
  [DATA_IMPORT_MODE.UPDATE_EXISTING]: 'data_transfer_mode_value_update_existing',
  [DATA_IMPORT_MODE.MIRROR_IMPORTED_SET]: 'data_transfer_mode_value_mirror_imported_set',
}

const warningDefinitions: Record<string, { label: MessageKey; detail: MessageKey }> = {
  invalid_count: { label: 'data_transfer_warning_invalid_count_label', detail: 'data_transfer_warning_invalid_count_detail' },
  unsupported_files: { label: 'data_transfer_warning_unsupported_files_label', detail: 'data_transfer_warning_unsupported_files_detail' },
  unsupported_records: { label: 'data_transfer_warning_unsupported_records_label', detail: 'data_transfer_warning_unsupported_records_detail' },
  skipped_non_tmdb: { label: 'data_transfer_warning_skipped_non_tmdb_label', detail: 'data_transfer_warning_skipped_non_tmdb_detail' },
  skipped_unsupported_media_type: { label: 'data_transfer_warning_skipped_media_type_label', detail: 'data_transfer_warning_skipped_media_type_detail' },
  skipped_invalid_status: { label: 'data_transfer_warning_skipped_status_label', detail: 'data_transfer_warning_skipped_status_detail' },
  skipped_invalid_rating: { label: 'data_transfer_warning_skipped_rating_label', detail: 'data_transfer_warning_skipped_rating_detail' },
  skipped_missing_tmdb_id: { label: 'data_transfer_warning_missing_tmdb_id_label', detail: 'data_transfer_warning_missing_tmdb_id_detail' },
  unresolved_episode_records: { label: 'data_transfer_warning_unresolved_episodes_label', detail: 'data_transfer_warning_unresolved_episodes_detail' },
  ambiguous_episode_parent: { label: 'data_transfer_warning_ambiguous_parent_label', detail: 'data_transfer_warning_ambiguous_parent_detail' },
  files_failed: { label: 'data_transfer_warning_files_failed_label', detail: 'data_transfer_warning_files_failed_detail' },
  metadata_errors: { label: 'data_transfer_warning_metadata_errors_label', detail: 'data_transfer_warning_metadata_errors_detail' },
}

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
const exportRunning = computed(() => {
  const status = latestExport.value?.status
  return status === DATA_TRANSFER_STATUS.PENDING || status === DATA_TRANSFER_STATUS.PROCESSING
})
const recentExports = computed(() => {
  return jobs.value
    .filter((job) => job.job_type === 'export')
    .sort((a, b) => instantEpochMs(b.created_at) - instantEpochMs(a.created_at))
    .slice(0, 7)
})
const deletingExportId = ref<number | null>(null)
const deleteExportDialog = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const pendingDeleteExportId = ref<number | null>(null)
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
    return modalJob.value.error_message || t('data_transfer_result_failed')
  }
  const imported = Number(finishedReport.value.records_imported || 0)
  const skipped = Number(finishedReport.value.records_skipped || 0)
  const unchanged = Number(finishedReport.value.records_unchanged || 0)
  const deleted = Number(finishedReport.value.deleted_total || 0)
  const lists = Number(finishedReport.value.lists_created || 0) + Number(finishedReport.value.lists_updated || 0)
  const listItems = Number(finishedReport.value.list_items_created || 0) + Number(finishedReport.value.list_items_updated || 0)
  const parts: string[] = []
  if (imported) parts.push(t('data_transfer_summary_imported', { count: imported }))
  if (deleted) parts.push(t('data_transfer_summary_deleted', { count: deleted }))
  if (skipped) parts.push(t('data_transfer_summary_skipped', { count: skipped }))
  if (unchanged) parts.push(t('data_transfer_summary_unchanged', { count: unchanged }))
  const listsUpdated = Number(finishedReport.value.lists_updated || 0)
  const deletedLists = Number(finishedReport.value.deleted?.lists || 0)
  const listItemsUpdated = Number(finishedReport.value.list_items_updated || 0)
  if (Number(finishedReport.value.lists_created || 0)) parts.push(t('data_transfer_summary_lists_created', { count: Number(finishedReport.value.lists_created) }))
  if (listsUpdated) parts.push(t('data_transfer_summary_lists_updated', { count: listsUpdated }))
  if (deletedLists) parts.push(t('data_transfer_summary_lists_removed', { count: deletedLists }))
  if (Number(finishedReport.value.list_items_created || 0)) parts.push(t('data_transfer_summary_list_items_added', { count: Number(finishedReport.value.list_items_created) }))
  if (listItemsUpdated) parts.push(t('data_transfer_summary_list_items_updated', { count: listItemsUpdated }))
  const deletedListItems = Number(finishedReport.value.list_items_deleted || 0)
  if (deletedListItems) parts.push(t('data_transfer_summary_list_items_removed', { count: deletedListItems }))
  return parts.length ? `${parts.join('. ')}.` : t('data_transfer_summary_empty')
})
const finishedStats = computed(() => [
  { label: t('data_transfer_stat_total'), value: finishedReport.value.records_seen ?? modalJob.value?.total_items ?? 0 },
  { label: t('data_transfer_stat_imported'), value: finishedReport.value.records_imported ?? 0 },
  { label: t('data_transfer_stat_skipped'), value: finishedReport.value.records_skipped ?? 0 },
  { label: t('data_transfer_stat_matched'), value: finishedReport.value.records_unchanged ?? 0 },
  { label: t('data_transfer_deleted'), value: finishedReport.value.deleted_total ?? 0 },
  { label: t('data_transfer_stat_metadata_errors'), value: finishedReport.value.metadata_errors ?? 0 },
])
const finishedCollections = computed(() => {
  const summary = finishedReport.value.summary
  const deleted = finishedReport.value.deleted
  return [
    {
      label: t('history_tab_title'),
      description: t('data_transfer_collection_history_desc'),
      found: Number(summary?.watch_history || 0),
      deleted: Number(deleted?.watch_history || 0),
    },
    {
      label: t('page_watchlist'),
      description: t('data_transfer_collection_watchlist_desc'),
      found: Number(summary?.watchlist || 0),
      deleted: Number(deleted?.watchlist || 0),
    },
    {
      label: t('profile_stat_ratings'),
      description: t('data_transfer_collection_ratings_desc'),
      found: Number(summary?.ratings || 0),
      deleted: Number(deleted?.ratings || 0),
    },
    {
      label: t('nav_lists'),
      description: t('data_transfer_collection_lists_desc'),
      found: Number(summary?.lists || 0),
      deleted: Number(deleted?.lists || 0),
    },
  ]
})
const finishedFiles = computed<DataTransferFileReport[]>(() => Array.isArray(finishedReport.value.files) ? finishedReport.value.files : [])
const finishedListDetails = computed<DataTransferListDetail[]>(() => Array.isArray(finishedReport.value.list_details) ? finishedReport.value.list_details : [])
const finishedWarningDetails = computed(() => {
  const report = finishedReport.value
  const warnings: FinishedWarning[] = []
  if (Array.isArray(report.warnings)) {
    report.warnings.forEach((warning, index) => warnings.push({
      key: `${warning.code || 'warning'}-${index}`,
      label: humanWarningCode(warning.code),
      value: formatWarningLocation(warning.location),
      detail: warning.message || t('data_transfer_warning_default_detail'),
    }))
  }
  Object.entries(warningDefinitions).forEach(([key, definition]) => {
    if (Number(report[key] || 0) > 0) warnings.push({
      key: `aggregate-${key}`,
      label: t(definition.label),
      value: String(report[key]),
      detail: t(definition.detail),
    })
  })
  const failedFiles = finishedFiles.value.filter((file) => file.status === 'failed')
  failedFiles.forEach((file) => warnings.push({
    key: `file-${file.file}`,
    label: file.file,
    value: t('data_transfer_failed'),
    detail: file.error || t('data_transfer_file_failed_detail'),
  }))
  return warnings
})

function humanWarningCode(code: string | undefined) {
  if (!code) return t('data_transfer_warning_default_label')
  const title = String(code).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
  return title.replace('Tmdb', 'TMDB')
}

function formatWarningLocation(location: DataTransferWarning['location'] = {}) {
  if (location.kind === 'csv_row') {
    const file = location.file || t('data_transfer_location_csv_file')
    return location.column
      ? t('data_transfer_location_csv_row_column', { file, row: location.row, column: location.column })
      : t('data_transfer_location_csv_row', { file, row: location.row })
  }
  if (location.kind === 'zip_record') return t('data_transfer_location_zip_record', { file: location.file || t('data_transfer_location_zip_entry'), record: location.record })
  if (location.kind === 'zip_file') return `${location.file || t('data_transfer_location_zip_entry')}`
  if (location.kind === 'json_item') {
    const collection = location.collection || t('data_transfer_location_json_collection')
    return location.field
      ? t('data_transfer_location_json_item_field', { collection, index: location.index, field: location.field })
      : t('data_transfer_location_json_item', { collection, index: location.index })
  }
  return t('data_transfer_location_unavailable')
}
function progressTotal(job: DataTransferJob) {
  return job.total_items || 0
}
function stageLabel(job: DataTransferJob) {
  if (job.status !== 'processing') return ''
  const stage = job.metadata?.pipeline?.stage
  if (stage === 'resolving_episodes') return t('data_transfer_stage_resolving')
  if (stage === 'finalizing') return t('data_transfer_stage_finalizing')
  return t('data_transfer_stage_importing')
}
const modalIsPreparing = computed(() => {
  if (!modalJob.value) return false
  return modalJob.value.status === DATA_TRANSFER_STATUS.PENDING || modalJob.value.status === DATA_TRANSFER_STATUS.PROCESSING
})
const modalCanConfirm = computed(() => modalJob.value?.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION)
const confirmErrorMessage = computed(() => {
  if (!confirmErrorCode.value) return ''
  const key = actionErrorKeys[confirmErrorCode.value]
  return key ? t(key) : t('data_transfer_error_action_default')
})

let timer: ReturnType<typeof setInterval> | null = null
const pollError = ref('')

async function pollJob(jobId: number) {
  if (timer !== null) clearInterval(timer)
  pollError.value = ''
  timer = setInterval(async () => {
    try {
      const status = await trackingAPI.getJobStatus(jobId)
      pollError.value = ''
      updateJob(status)
      if (
        status?.status === DATA_TRANSFER_STATUS.AWAITING_CONFIRMATION
        || status?.status === DATA_TRANSFER_STATUS.DONE
        || status?.status === DATA_TRANSFER_STATUS.FAILED
        || status?.status === DATA_TRANSFER_STATUS.CANCELLED
      ) {
        if (timer !== null) clearInterval(timer)
        timer = null
        await loadJobs()
      }
    } catch {
      // Keep polling through transient network failures so a blip cannot
      // strand a job in "processing" forever; the message tells the user.
      pollError.value = t('data_transfer_poll_error')
    }
  }, 1500)
}

function handleZipFileSelect(event: Event) {
  zipError.value = ''
  zipFile.value = selectedFile(event)
  zipFileName.value = zipFile.value?.name || ''
}

function handleWetrakrFileSelect(event: Event) {
  wetrakrError.value = ''
  wetrakrFile.value = selectedFile(event)
  wetrakrFileName.value = wetrakrFile.value?.name || ''
}

function handleYamtrackFileSelect(event: Event) {
  yamtrackError.value = ''
  yamtrackFile.value = selectedFile(event)
  yamtrackFileName.value = yamtrackFile.value?.name || ''
}

function handleArxmediaFileSelect(event: Event) {
  arxmediaError.value = ''
  arxmediaFile.value = selectedFile(event)
  arxmediaFileName.value = arxmediaFile.value?.name || ''
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
    zipError.value = t('data_transfer_error_choose_trakt')
    zipFileName.value = ''
    return
  }
  if (!file.name.toLowerCase().endsWith('.zip')) {
    zipError.value = t('data_transfer_error_zip_only')
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
    zipError.value = getApiErrorMessage(error, t('data_transfer_error_zip_start'))
  }
}

async function startWetrakrImport() {
  wetrakrError.value = ''
  confirmErrorCode.value = ''
  const file = wetrakrFile.value
  if (!file) {
    wetrakrError.value = t('data_transfer_error_choose_wetrakr')
    wetrakrFileName.value = ''
    return
  }
  if (!file.name.toLowerCase().endsWith('.zip')) {
    wetrakrError.value = t('data_transfer_error_zip_only')
    return
  }
  try {
    const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.ZIP, 'wetrakr')
    updateJob(created)
    selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
    modalJobId.value = created.id
    showImportModeModal.value = true
    await pollJob(created.id)
  } catch (error) {
    wetrakrError.value = getApiErrorMessage(error, t('data_transfer_error_wetrakr_start'))
  }
}

async function startYamtrackImport() {
  yamtrackError.value = ''
  confirmErrorCode.value = ''
  const file = yamtrackFile.value
  if (!file) {
    yamtrackError.value = t('data_transfer_error_choose_yamtrack')
    yamtrackFileName.value = ''
    return
  }
  if (!file.name.toLowerCase().endsWith('.csv')) {
    yamtrackError.value = t('data_transfer_error_csv_only')
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
    yamtrackError.value = getApiErrorMessage(error, t('data_transfer_error_csv_start'))
  }
}

async function startArxmediaImport() {
  arxmediaError.value = ''
  confirmErrorCode.value = ''
  const file = arxmediaFile.value
  if (!file) {
    arxmediaError.value = t('data_transfer_error_choose_arxmedia')
    arxmediaFileName.value = ''
    return
  }
  if (!file.name.toLowerCase().endsWith('.zip')) {
    arxmediaError.value = t('data_transfer_error_arxmedia_zip_only')
    return
  }
  try {
    const created = await trackingAPI.importData(file, DATA_TRANSFER_FORMAT.ZIP, 'arxmedia')
    updateJob(created)
    selectedImportMode.value = DATA_IMPORT_MODE.NEW_ITEMS
    modalJobId.value = created.id
    showImportModeModal.value = true
    await pollJob(created.id)
  } catch (error) {
    arxmediaError.value = getApiErrorMessage(error, t('data_transfer_error_arxmedia_start'))
  }
}

function askDeleteExport(jobId: number) {
  pendingDeleteExportId.value = jobId
  deleteExportDialog.value?.showModal()
}

async function confirmDeleteExport() {
  const jobId = pendingDeleteExportId.value
  if (jobId === null || deletingExportId.value !== null) return
  deletingExportId.value = jobId
  exportError.value = ''
  try {
    const updated = await trackingAPI.deleteExportFile(jobId)
    updateJob(updated)
    pendingDeleteExportId.value = null
    deleteExportDialog.value?.close()
  } catch (error) {
    exportError.value = getApiErrorMessage(error, t('data_transfer_error_delete_export'))
  } finally {
    deletingExportId.value = null
  }
}

const exportStatusById = computed<Record<number, { text: string; className: string }>>(() => {
  return Object.fromEntries(recentExports.value.map((job) => {
    if (job.job_type === 'export' && job.status === DATA_TRANSFER_STATUS.DONE && !job.output_url) {
      return [job.id, { text: t('data_transfer_deleted'), className: 'text-red-400' }]
    }
    return [job.id, { text: humanStatus(job.status), className: statusClass(job.status) }]
  }))
})

async function startExport() {
  exportError.value = ''
  try {
    const created = await trackingAPI.exportData(DATA_TRANSFER_FORMAT.ZIP)
    updateJob(created)
    await pollJob(created.id)
  } catch (error) {
    exportError.value = getApiErrorMessage(error, t('data_transfer_error_export_start'))
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
  jobs.value = data.results || []
}

function latestProcessingJob() {
  return jobs.value
    .filter((job) => job?.status === DATA_TRANSFER_STATUS.PROCESSING)
    .sort((a, b) => instantEpochMs(b.created_at) - instantEpochMs(a.created_at))[0] || null
}

function humanStatus(value: DataTransferStatus | undefined) {
  const key = value ? statusKeys[value] : undefined
  return key ? t(key) : String(value || '').replaceAll('_', ' ')
}

function humanValue(value: string | undefined) {
  const labels: Record<string, string> = {
    arxmedia: 'ArxMedia',
    trakt: 'Trakt',
    wetrakr: 'WeTrackr',
    yamtrack: 'Yamtrack',
  }
  const modeKey = value ? importModeValueKeys[value] : undefined
  if (modeKey) return t(modeKey)
  return labels[String(value)] || String(value || t('data_transfer_unknown')).replaceAll('_', ' ')
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
