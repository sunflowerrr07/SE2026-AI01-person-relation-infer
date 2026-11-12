import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useDashboard } from './store'

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('dashboard workflow', () => {
  it('uploads authorized media, starts analysis and loads graph and audit records', async () => {
    const responses = [
      { media_id: 'M1' }, { task_id: 'T1' }, {}, [{ task_id: 'T1', status: 'succeeded' }],
      [{ person_id: 'A' }, { person_id: 'B' }], [{ source: 'A', target: 'B', confidence: 0.5 }],
      { synthetic_input: true, windows: [] }, [{ actor: 'alice', outcome: 'success' }]
    ]
    const fetcher = vi.fn().mockImplementation(async () => ({ ok: true, json: async () => ({ data: responses.shift() }) }))
    vi.stubGlobal('fetch', fetcher)
    const store = useDashboard()
    store.token = 'test-token'
    expect(await store.upload(new File(['mock'], 'test.png', { type: 'image/png' }))).toBe('T1')
    expect(fetcher.mock.calls[0][1].body.get('authorized')).toBe('true')
    expect(fetcher.mock.calls[2][0]).toBe('/api/v1/tasks/T1/run-demo')
    await store.loadGraph('T1')
    expect(store.people).toHaveLength(2)
    expect(store.result.synthetic_input).toBe(true)
    await store.loadAudit()
    expect(store.events[0].actor).toBe('alice')
  })
})
