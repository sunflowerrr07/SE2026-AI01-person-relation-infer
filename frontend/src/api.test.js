import { describe, it, expect, vi, afterEach } from 'vitest'
import { request, graphOption } from './api'

afterEach(() => vi.restoreAllMocks())
describe('API and graph contracts', () => {
  it('sends bearer authorization and unwraps server response', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [{ task_id: 'T1' }] }) })
    vi.stubGlobal('fetch', fetcher)
    expect(await request('/api/v1/tasks', 'secret')).toEqual([{ task_id: 'T1' }])
    expect(fetcher.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer secret')
  })
  it('surfaces unauthorized responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403 }))
    await expect(request('/api/v1/audit/events', 'x')).rejects.toThrow('403')
  })
  it('maps nodes and relationship evidence into a graph', () => {
    const option = graphOption([{ person_id: 'A' }, { person_id: 'B' }], [{ source: 'A', target: 'B', confidence: 0.75, uncertain: true }])
    expect(option.series[0].data.map(x => x.id)).toEqual(['A', 'B'])
    expect(option.series[0].links[0]).toMatchObject({ source: 'A', target: 'B', value: 0.75 })
  })
})
