import { defineStore } from 'pinia'
import { request } from './api'

export const useDashboard = defineStore('dashboard', {
  state: () => ({ token: '', tasks: [], selected: '', people: [], relations: [], result: null, events: [], neighbors: [], error: '', busy: false }),
  actions: {
    async call(path, options) { return request(path, this.token, options) },
    async refreshTasks() { this.tasks = await this.call('/api/v1/tasks') },
    async upload(file) {
      const data = new FormData()
      data.append('file', file)
      data.append('authorized', 'true')
      const media = await this.call('/api/v1/media', { method: 'POST', body: data })
      const task = await this.call('/api/v1/tasks/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ media_id: media.media_id }) })
      this.selected = task.task_id
      await this.call(`/api/v1/tasks/${encodeURIComponent(task.task_id)}/run-demo`, { method: 'POST' })
      await this.refreshTasks()
      return task.task_id
    },
    async loadGraph(taskId) {
      this.selected = taskId
      const query = `?task_id=${encodeURIComponent(taskId)}`
      const [people, relations, result] = await Promise.all([
        this.call('/api/v1/graph/persons' + query), this.call('/api/v1/graph/relations' + query),
        this.call(`/api/v1/tasks/${encodeURIComponent(taskId)}/result`)
      ])
      this.people = people; this.relations = relations; this.result = result; this.neighbors = []
    },
    async loadNeighbors(personId, hops) {
      this.neighbors = await this.call(`/api/v1/graph/persons/${encodeURIComponent(personId)}/neighbors?task_id=${encodeURIComponent(this.selected)}&max_hops=${hops}`)
    },
    async loadAudit() { this.events = await this.call('/api/v1/audit/events') }
  }
})
