import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { apiGet, apiPost } from '@/api/client'

const ADMIN_TOKEN_KEY = 'admin_token'
const MAX_LOGS = 500

type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'DEBUG' | string
type TestMessageType = 'stdout' | 'stderr' | 'exit'
type PipelineStatus = 'pending' | 'running' | 'success' | 'failed' | string

export interface LogEntry {
  id: number | string
  timestamp: string
  level: LogLevel
  source: string
  message: string
}

export interface PipelineEvent {
  event?: string
  step_name: string
  step_index: number
  total_steps: number
  status: PipelineStatus
  duration_ms?: number
  error?: string | null
  timestamp?: string
}

export interface TestLine {
  type: TestMessageType
  line: string
  exit_code?: number
  summary?: TestSummary
  timestamp: string
}

export interface TestSummary {
  passed?: number
  failed?: number
  warnings?: number
}

interface TestRunResponse {
  run_id: string
  status: string
}

interface LogHistoryResponse {
  items: LogEntry[]
  total?: number
  offset?: number
  limit?: number
}

interface PipelineLastResponse {
  events?: PipelineEvent[]
}

interface TestLastResponse {
  output?: Omit<TestLine, 'timestamp'>[]
}

interface LogFilesResponse {
  files?: string[]
}

function getToken(): string {
  if (typeof window === 'undefined') {
    return ''
  }
  return window.localStorage.getItem(ADMIN_TOKEN_KEY) ?? ''
}

function normalizeWsBase(): string {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'
  const baseUrl = new URL(apiBase, window.location.origin)
  const protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  const pathname = baseUrl.pathname.replace(/\/api\/?$/, '')
  return `${protocol}//${baseUrl.host}${pathname}`
}

function formatWsUrl(path: string): string {
  const token = getToken()
  const wsUrl = new URL(path, normalizeWsBase())
  if (token) {
    wsUrl.searchParams.set('token', token)
  }
  return wsUrl.toString()
}

function limitLogs(items: LogEntry[]): LogEntry[] {
  if (items.length <= MAX_LOGS) {
    return items
  }
  return items.slice(items.length - MAX_LOGS)
}

export const useDevtoolsStore = defineStore('devtools', () => {
  const logs = ref<LogEntry[]>([])
  const pipelineEvents = ref<PipelineEvent[]>([])
  const testOutput = ref<TestLine[]>([])
  const testRunning = ref(false)
  const logsPaused = ref(false)
  const logsConnected = ref(false)
  const pipelineConnected = ref(false)
  const testConnected = ref(false)
  const loading = ref(false)
  const error = ref('')
  const logFiles = ref<string[]>([])
  const logHistory = ref<LogEntry[]>([])
  const logHistoryTotal = ref(0)

  const logsFilter = reactive({
    level: 'ALL',
    source: 'ALL',
    search: ''
  })

  let logsSocket: WebSocket | null = null
  let pipelineSocket: WebSocket | null = null
  let testSocket: WebSocket | null = null

  const filteredLogs = computed(() => {
    const keyword = logsFilter.search.trim().toLowerCase()
    return logs.value.filter((entry) => {
      const levelText = String(entry.level ?? '').toUpperCase()
      const sourceText = String(entry.source ?? '')
      const messageText = String(entry.message ?? '')
      const matchedLevel = logsFilter.level === 'ALL' || levelText === logsFilter.level
      const matchedSource = logsFilter.source === 'ALL' || sourceText === logsFilter.source
      const matchedKeyword =
        keyword.length === 0 ||
        messageText.toLowerCase().includes(keyword) ||
        sourceText.toLowerCase().includes(keyword) ||
        levelText.toLowerCase().includes(keyword)
      return matchedLevel && matchedSource && matchedKeyword
    })
  })

  const connectLogsWs = () => {
    if (typeof window === 'undefined') {
      return
    }
    if (logsSocket && logsSocket.readyState === WebSocket.OPEN) {
      return
    }
    disconnectLogsWs()
    logsSocket = new WebSocket(formatWsUrl('/ws/logs'))

    logsSocket.onopen = () => {
      logsConnected.value = true
      error.value = ''
    }

    logsSocket.onmessage = (messageEvent) => {
      if (logsPaused.value) {
        return
      }
      try {
        const payload = JSON.parse(messageEvent.data) as LogEntry
        logs.value = limitLogs([...logs.value, payload])
      } catch (err) {
        error.value = err instanceof Error ? err.message : '日志流解析失败'
      }
    }

    logsSocket.onerror = () => {
      error.value = '日志连接异常'
    }

    logsSocket.onclose = () => {
      logsConnected.value = false
      logsSocket = null
    }
  }

  const disconnectLogsWs = () => {
    if (logsSocket) {
      logsSocket.close()
      logsSocket = null
    }
    logsConnected.value = false
  }

  const connectPipelineWs = () => {
    if (typeof window === 'undefined') {
      return
    }
    if (pipelineSocket && pipelineSocket.readyState === WebSocket.OPEN) {
      return
    }
    disconnectPipelineWs()
    pipelineSocket = new WebSocket(formatWsUrl('/ws/pipeline'))

    pipelineSocket.onopen = () => {
      pipelineConnected.value = true
      error.value = ''
    }

    pipelineSocket.onmessage = (messageEvent) => {
      try {
        const payload = JSON.parse(messageEvent.data) as PipelineEvent
        pipelineEvents.value = [...pipelineEvents.value, payload]
      } catch (err) {
        error.value = err instanceof Error ? err.message : '流水线事件解析失败'
      }
    }

    pipelineSocket.onerror = () => {
      error.value = '流水线连接异常'
    }

    pipelineSocket.onclose = () => {
      pipelineConnected.value = false
      pipelineSocket = null
    }
  }

  const disconnectPipelineWs = () => {
    if (pipelineSocket) {
      pipelineSocket.close()
      pipelineSocket = null
    }
    pipelineConnected.value = false
  }

  const connectTestWs = () => {
    if (typeof window === 'undefined') {
      return
    }
    if (testSocket && (testSocket.readyState === WebSocket.CONNECTING || testSocket.readyState === WebSocket.OPEN)) {
      return
    }
    disconnectTestWs()
    testSocket = new WebSocket(formatWsUrl('/ws/test'))

    testSocket.onopen = () => {
      testConnected.value = true
      error.value = ''
    }

    testSocket.onmessage = (messageEvent) => {
      try {
        const payload = JSON.parse(messageEvent.data) as Omit<TestLine, 'timestamp'>
        const line: TestLine = {
          ...payload,
          timestamp: new Date().toISOString()
        }
        testOutput.value = [...testOutput.value, line]
        if (payload.type === 'exit') {
          testRunning.value = false
        }
      } catch (err) {
        error.value = err instanceof Error ? err.message : '测试输出解析失败'
      }
    }

    testSocket.onerror = () => {
      error.value = '测试连接异常'
    }

    testSocket.onclose = () => {
      testConnected.value = false
      testSocket = null
    }
  }

  const disconnectTestWs = () => {
    if (testSocket) {
      testSocket.close()
      testSocket = null
    }
    testConnected.value = false
  }

  const runTest = async (testFile?: string) => {
    loading.value = true
    error.value = ''
    testRunning.value = true
    testOutput.value = []

    try {
      connectTestWs()
      return await apiPost<TestRunResponse>('/devtools/test', {
        ...(testFile?.trim() ? { test_file: testFile.trim() } : {})
      })
    } catch (err) {
      testRunning.value = false
      error.value = err instanceof Error ? err.message : '触发测试失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchLastPipelineEvents = async () => {
    loading.value = true
    error.value = ''
    try {
      const response = await apiGet<PipelineEvent[] | PipelineLastResponse>('/devtools/pipeline/last')
      if (Array.isArray(response)) {
        pipelineEvents.value = response
      } else if (Array.isArray(response?.events)) {
        pipelineEvents.value = response.events
      } else {
        pipelineEvents.value = []
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载最近流水线失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchLastTestOutput = async () => {
    loading.value = true
    error.value = ''
    try {
      const response = await apiGet<Omit<TestLine, 'timestamp'>[] | TestLastResponse>('/devtools/test/last')
      const items = Array.isArray(response) ? response : Array.isArray(response?.output) ? response.output : []
      testOutput.value = items.map((item) => ({
        ...item,
        timestamp: new Date().toISOString()
      }))
      const lastLine = items.length > 0 ? items[items.length - 1] : undefined
      testRunning.value = lastLine?.type !== 'exit'
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载最近测试失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchLogFiles = async () => {
    loading.value = true
    error.value = ''
    try {
      const response = await apiGet<string[] | LogFilesResponse>('/devtools/logs/files')
      const files = Array.isArray(response) ? response : Array.isArray(response?.files) ? response.files : []
      logFiles.value = files
      return files
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载日志文件失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchLogHistory = async (file: string, offset = 0, limit = 100) => {
    loading.value = true
    error.value = ''
    try {
      const query = new URLSearchParams({
        file,
        offset: String(offset),
        limit: String(limit)
      })
      const response = await apiGet<LogHistoryResponse | LogEntry[]>(`/devtools/logs/history?${query.toString()}`)
      if (Array.isArray(response)) {
        logHistory.value = response
        logHistoryTotal.value = response.length
      } else {
        logHistory.value = response.items
        logHistoryTotal.value = response.total ?? response.items.length
      }
      return logHistory.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载历史日志失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const clearRealtimeLogs = () => {
    logs.value = []
  }

  return {
    logs,
    pipelineEvents,
    testOutput,
    testRunning,
    logsPaused,
    logsFilter,
    filteredLogs,
    logsConnected,
    pipelineConnected,
    testConnected,
    loading,
    error,
    logFiles,
    logHistory,
    logHistoryTotal,
    connectLogsWs,
    disconnectLogsWs,
    connectPipelineWs,
    disconnectPipelineWs,
    connectTestWs,
    disconnectTestWs,
    runTest,
    fetchLastPipelineEvents,
    fetchLastTestOutput,
    fetchLogFiles,
    fetchLogHistory,
    clearRealtimeLogs
  }
})
