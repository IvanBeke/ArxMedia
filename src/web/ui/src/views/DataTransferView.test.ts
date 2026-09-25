import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import DataTransferView from '@/views/DataTransferView.vue'
import { DATA_TRANSFER_STATUS } from '@/constants/tracking'

const { deleteExportFile, exportData, getJobStatus, importData, listJobs } = vi.hoisted(() => ({
  deleteExportFile: vi.fn(),
  exportData: vi.fn(),
  getJobStatus: vi.fn(),
  importData: vi.fn(),
  listJobs: vi.fn(),
}))

vi.mock('@/api', () => {
  return {
    trackingAPI: {
      deleteExportFile,
      exportData,
      getJobStatus,
      importData,
      listJobs,
    },
  }
})

function mountView(jobs: object[]) {
  listJobs.mockResolvedValueOnce(jobs)
  return mount(DataTransferView, { global: { plugins: [createPinia()] } })
}

// Fixtures stay inside the view's "last 7 days" filter regardless of when
// the suite runs (fixed dates age out and the jobs vanish from the list).
function recentIso(offsetMs = 0): string {
  return new Date(Date.now() - 2 * 24 * 60 * 60 * 1000 + offsetMs).toISOString()
}

function pendingJob(overrides: Record<string, unknown> = {}) {
  return {
    id: 99,
    job_type: 'import',
    status: DATA_TRANSFER_STATUS.PENDING,
    created_at: recentIso(),
    updated_at: recentIso(),
    processed_items: 0,
    total_items: 0,
    ...overrides,
  }
}

describe('DataTransferView', () => {
  beforeEach(() => {
    deleteExportFile.mockReset()
    exportData.mockReset()
    getJobStatus.mockReset()
    importData.mockReset()
    listJobs.mockReset()
  })

  it('opens completed import details with report counters and warnings', async () => {
    const wrapper = mountView([{
      id: 12,
      job_type: 'import',
      data_format: 'csv',
      source: 'yamtrack',
      import_mode: 'update_existing',
      status: DATA_TRANSFER_STATUS.DONE,
      total_items: 10,
      processed_items: 10,
      created_at: recentIso(),
      updated_at: recentIso(60_000),
      metadata: {
        report: {
          records_seen: 10,
          records_imported: 7,
          records_skipped: 3,
          records_unchanged: 0,
          metadata_errors: 1,
          skipped_non_tmdb: 2,
          deleted_total: 4,
          deleted: { watch_history: 3, ratings: 1 },
          warnings: [{
            code: 'missing_tmdb_id',
            message: 'The row does not contain a TMDB ID.',
            location: { kind: 'csv_row', file: 'yamtrack.csv', row: 18, column: 'media_id' },
          }],
        },
      },
    }])
    await flushPromises()

    const completedJob = wrapper.findAll('div.cursor-pointer').find((item) => item.text().includes('done'))
    if (!completedJob) throw new Error('Completed import job was not rendered')
    await completedJob.trigger('click')

    expect(wrapper.text()).toContain('What happened?')
    expect(wrapper.text()).toContain('Total records')
    expect(wrapper.text()).toContain('Imported')
    expect(wrapper.text()).toContain('Skipped')
    expect(wrapper.text()).toContain('Yamtrack CSV import')
    expect(wrapper.text()).toContain('What was imported')
    expect(wrapper.text()).toContain('Deleted')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('3 deleted')
    await wrapper.find('summary').trigger('click')
    expect(wrapper.text()).toContain('Metadata lookups failed')
    expect(wrapper.text()).toContain('Non-TMDB rows skipped')
  })

  it('shows job and file errors for failed imports', async () => {
    const wrapper = mountView([{
      id: 13,
      job_type: 'import',
      data_format: 'zip',
      source: 'trakt',
      status: DATA_TRANSFER_STATUS.FAILED,
      created_at: recentIso(),
      updated_at: recentIso(60_000),
      error_message: 'Import worker stopped.',
      metadata: {
        report: {
          files_failed: 1,
          files: [{ file: 'watched-history.json', status: 'failed', error: 'Invalid JSON' }],
        },
      },
    }])
    await flushPromises()

    const failedJob = wrapper.findAll('div.cursor-pointer').find((item) => item.text().includes('failed'))
    if (!failedJob) throw new Error('Failed import job was not rendered')
    await failedJob.trigger('click')

    expect(wrapper.text()).toContain('Job error')
    expect(wrapper.text()).toContain('Import worker stopped.')
    expect(wrapper.text()).toContain('watched-history.json')
    expect(wrapper.text()).toContain('Invalid JSON')
    expect(wrapper.find('details').exists()).toBe(true)
    expect(wrapper.find('details').element.open).toBe(false)
  })

  it('shows the selected WeTrackr ZIP filename and enables upload', async () => {
    const wrapper = mountView([])
    await flushPromises()

    const input = wrapper.find('input[aria-label="Import WeTrackr ZIP"]')
    const file = new File(['zip'], 'wetrakr_export_user.zip', { type: 'application/zip' })
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })

    await input.trigger('change')

    expect(wrapper.text()).toContain('wetrakr_export_user.zip')
    const uploadButtons = wrapper.findAll('button').filter((button) => button.text() === 'Upload ZIP')
    expect(uploadButtons).toHaveLength(2)
    expect(uploadButtons[0]?.attributes('disabled')).toBeDefined()
    expect(uploadButtons[1]?.attributes('disabled')).toBeUndefined()
  })

  it('uploads WeTrackr files with the ZIP source format', async () => {
    const wrapper = mountView([])
    await flushPromises()
    importData.mockResolvedValue(pendingJob({ source: 'wetrakr', data_format: 'zip' }))

    const input = wrapper.find('input[aria-label="Import WeTrackr ZIP"]')
    const file = new File(['zip'], 'wetrakr_export_user.zip', { type: 'application/zip' })
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    const uploadButtons = wrapper.findAll('button').filter((button) => button.text() === 'Upload ZIP')
    await uploadButtons[1]?.trigger('click')
    await flushPromises()

    expect(importData).toHaveBeenCalledWith(file, 'zip', 'wetrakr')
    wrapper.unmount()
  })

  it('uploads new ArxMedia exports as ZIP backups', async () => {
    const wrapper = mountView([])
    await flushPromises()
    importData.mockResolvedValue(pendingJob({ source: 'arxmedia', data_format: 'zip' }))

    const input = wrapper.find('input[aria-label="Import ArxMedia backup"]')
    const file = new File(['zip'], 'backup.zip', { type: 'application/zip' })
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    const uploadButton = wrapper.findAll('button').find((button) => button.text() === 'Upload backup')
    await uploadButton?.trigger('click')
    await flushPromises()

    expect(importData).toHaveBeenCalledWith(file, 'zip', 'arxmedia')
    wrapper.unmount()
  })

  it('creates ZIP exports', async () => {
    const wrapper = mountView([])
    await flushPromises()
    exportData.mockResolvedValue(pendingJob({ job_type: 'export', data_format: 'zip' }))

    const exportButton = wrapper.findAll('button').find((button) => button.text() === 'Create export')
    await exportButton?.trigger('click')
    await flushPromises()

    expect(exportData).toHaveBeenCalledWith('zip')
    wrapper.unmount()
  })

  it('shows the selected ArxMedia backup filename and enables upload', async () => {
    const wrapper = mountView([])
    await flushPromises()

    const input = wrapper.find('input[aria-label="Import ArxMedia backup"]')
    const file = new File(['zip'], 'backup.zip', { type: 'application/zip' })
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })

    await input.trigger('change')

    expect(wrapper.text()).toContain('backup.zip')
    const uploadButton = wrapper.findAll('button').find((button) => button.text() === 'Upload backup')
    expect(uploadButton?.attributes('disabled')).toBeUndefined()
  })

  it('normalizes paginated job responses before rendering', async () => {
    listJobs.mockReset()
    listJobs.mockResolvedValueOnce({
      results: [{
        id: 14,
        job_type: 'import',
        data_format: 'zip',
        source: 'arxmedia',
        status: DATA_TRANSFER_STATUS.DONE,
        total_items: 1,
        processed_items: 1,
        created_at: recentIso(),
        updated_at: recentIso(60_000),
      }],
    })

    const wrapper = mount(DataTransferView, { global: { plugins: [createPinia()] } })
    await flushPromises()

    expect(wrapper.text()).toContain('done')
    expect(wrapper.text()).not.toContain('No import jobs from the last 7 days.')
  })

  it('shows lists in the completed import report', async () => {
    const wrapper = mountView([{
      id: 15,
      job_type: 'import',
      data_format: 'json',
      source: 'arxmedia',
      status: DATA_TRANSFER_STATUS.DONE,
      total_items: 3,
      processed_items: 3,
      created_at: recentIso(),
      updated_at: recentIso(60_000),
      metadata: {
        report: {
          records_seen: 1,
          records_imported: 1,
          lists_created: 1,
          list_items_created: 2,
          summary: { lists: 1 },
          deleted: { lists: 1 },
        },
      },
    }])
    await flushPromises()

    const completedJob = wrapper.findAll('div.cursor-pointer').find((item) => item.text().includes('done'))
    if (!completedJob) throw new Error('Completed import job was not rendered')
    await completedJob.trigger('click')

    expect(wrapper.text()).toContain('Lists')
    expect(wrapper.text()).toContain('1 found')
    expect(wrapper.text()).toContain('1 deleted')
    expect(wrapper.text()).toContain('1 lists created')
    expect(wrapper.text()).toContain('2 list items added')
  })
})
