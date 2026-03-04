import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiDelete, apiGet } from '@/api/client'

export interface LogEntry {
  id: number
  timestamp: string
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG' | string
  message: string
  source: string
  metadata: Record<string, unknown> | null
}

export interface LogsQuery {
  page?: number
  limit?: number
  level?: string
  source?: string
  search?: string
}

interface LogsResponse {
  items: LogEntry[]
  total: number
  page: number
}

function buildQuery(params: LogsQuery = {}): string {
  const query = new URLSearchParams()

  if (params.page) {
    query.set('page', String(params.page))
  }
  if (params.limit) {
    query.set('limit', String(params.limit))
  }
  if (params.level && params.level !== 'ALL') {
    query.set('level', params.level)
  }
  if (params.source && params.source !== 'ALL') {
    query.set('source', params.source)
  }
  if (params.search && params.search.trim()) {
    query.set('search', params.search.trim())
  }

  const queryString = query.toString()
  return queryString ? `/logs?${queryString}` : '/logs'
}

export const useLogsStore = defineStore('logs', () => {
  const logs = ref<LogEntry[]>([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const error = ref('')

  const fetchLogs = async (params: LogsQuery = {}) => {
    loading.value = true
    error.value = ''

    try {
      const response = await apiGet<LogsResponse>(buildQuery(params))
      logs.value = response.items
      total.value = response.total
      page.value = response.page
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载日志失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const clearLogs = async () => {
    loading.value = true
    error.value = ''

    try {
      await apiDelete('/logs')
      logs.value = []
      total.value = 0
      page.value = 1
    } catch (err) {
      error.value = err instanceof Error ? err.message : '清空日志失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    logs,
    total,
    page,
    loading,
    error,
    fetchLogs,
    clearLogs
  }
})
