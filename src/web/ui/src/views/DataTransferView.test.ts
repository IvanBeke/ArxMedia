import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import DataTransferView from '@/views/DataTransferView.vue'
import { DATA_TRANSFER_STATUS } from '@/constants/tracking'

const { listJobs } = vi.hoisted(() => ({ listJobs: vi.fn() }))

vi.mock('@/api', () => {
  return {
    trackingAPI: {
      listJobs,
    },
  }
})

function mountView(jobs: object[]) {
  listJobs.mockResolvedValueOnce(jobs)
  return mount(DataTransferView, { global: { plugins: [createPinia()] } })
}

describe('DataTransferView', () => {
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
      created_at: '2026-09-08T10:00:00Z',
      updated_at: '2026-09-08T10:01:00Z',
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
    expect(wrapper.text()).toContain('yamtrack CSV import')
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
      created_at: '2026-09-08T10:00:00Z',
      updated_at: '2026-09-08T10:01:00Z',
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

  it('shows the selected JSON filename and enables upload', async () => {
    const wrapper = mountView([])
    await flushPromises()

    const input = wrapper.find('input[aria-label="Import ArxMedia JSON"]')
    const file = new File(['{}'], 'backup.json', { type: 'application/json' })
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })

    await input.trigger('change')

    expect(wrapper.text()).toContain('backup.json')
    expect(wrapper.find('button').element).toBeDefined()
    const uploadButton = wrapper.findAll('button').find((button) => button.text() === 'Upload JSON')
    expect(uploadButton?.attributes('disabled')).toBeUndefined()
  })

  it('normalizes paginated job responses before rendering', async () => {
    listJobs.mockReset()
    listJobs.mockResolvedValueOnce({
      results: [{
        id: 14,
        job_type: 'import',
        data_format: 'json',
        source: 'arxmedia',
        status: DATA_TRANSFER_STATUS.DONE,
        total_items: 1,
        processed_items: 1,
        created_at: '2026-09-08T10:00:00Z',
        updated_at: '2026-09-08T10:01:00Z',
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
      created_at: '2026-09-08T10:00:00Z',
      updated_at: '2026-09-08T10:01:00Z',
      metadata: {
        report: {
          records_seen: 1,
          records_imported: 1,
          lists_imported: 1,
          list_items_imported: 2,
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
    expect(wrapper.text()).toContain('1 lists imported')
    expect(wrapper.text()).toContain('2 list items imported')
  })
})
