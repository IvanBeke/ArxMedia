import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import DataTransferView from '@/views/DataTransferView.vue'
import { DATA_TRANSFER_STATUS } from '@/constants/tracking'

const listJobs = vi.fn()

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    trackingAPI: {
      ...actual.trackingAPI,
      listJobs: (...args) => listJobs(...args),
    },
  }
})

function mountView(jobs) {
  listJobs.mockResolvedValueOnce({ results: jobs })
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

    await wrapper.findAll('div.cursor-pointer').find((item) => item.text().includes('done')).trigger('click')

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

    await wrapper.findAll('div.cursor-pointer').find((item) => item.text().includes('failed')).trigger('click')

    expect(wrapper.text()).toContain('Job error')
    expect(wrapper.text()).toContain('Import worker stopped.')
    expect(wrapper.text()).toContain('watched-history.json')
    expect(wrapper.text()).toContain('Invalid JSON')
    expect(wrapper.find('details').exists()).toBe(true)
    expect(wrapper.find('details').element.open).toBe(false)
  })
})
