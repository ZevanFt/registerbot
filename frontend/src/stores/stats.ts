import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiGet } from '@/api/client'

export interface StatsSummary {
  total_requests: number
  total_tokens: number
  avg_latency: number
}

export interface HourlyItem {
  hour: number
  requests: number
}

export interface DailyItem {
  date: string
  requests: number
  tokens: number
}

export interface ModelDistributionItem {
  model: string
  requests: number
}

export interface AccountUsageItem {
  email: string
  requests: number
  total_tokens: number
}

export const defaultSummary: StatsSummary = {
  total_requests: 0,
  total_tokens: 0,
  avg_latency: 0
}

export const useStatsStore = defineStore('stats', () => {
  const summary = ref<StatsSummary>({ ...defaultSummary })
  const hourlyData = ref<HourlyItem[]>([])
  const dailyData = ref<DailyItem[]>([])
  const modelDist = ref<ModelDistributionItem[]>([])
  const accountUsage = ref<AccountUsageItem[]>([])
  const loading = ref(false)
  const error = ref('')

  const normalizeNumber = (value: unknown): number => {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }

  const normalizeSummary = (value: unknown): StatsSummary => {
    const raw = (value ?? {}) as Record<string, unknown>
    return {
      total_requests: normalizeNumber(raw.total_requests),
      total_tokens: normalizeNumber(raw.total_tokens),
      avg_latency: normalizeNumber(raw.avg_latency)
    }
  }

  const normalizeHourly = (value: unknown): HourlyItem[] => {
    if (!Array.isArray(value)) {
      return []
    }
    return value.map((item) => {
      const raw = (item ?? {}) as Record<string, unknown>
      return {
        hour: normalizeNumber(raw.hour),
        requests: normalizeNumber(raw.requests)
      }
    })
  }

  const normalizeDaily = (value: unknown): DailyItem[] => {
    if (!Array.isArray(value)) {
      return []
    }
    return value.map((item) => {
      const raw = (item ?? {}) as Record<string, unknown>
      return {
        date: String(raw.date ?? ''),
        requests: normalizeNumber(raw.requests),
        tokens: normalizeNumber(raw.tokens)
      }
    })
  }

  const normalizeModelDist = (value: unknown): ModelDistributionItem[] => {
    if (!Array.isArray(value)) {
      return []
    }
    return value.map((item) => {
      const raw = (item ?? {}) as Record<string, unknown>
      return {
        model: String(raw.model ?? 'unknown'),
        requests: normalizeNumber(raw.requests ?? raw.count)
      }
    })
  }

  const normalizeAccountUsage = (value: unknown): AccountUsageItem[] => {
    if (!Array.isArray(value)) {
      return []
    }
    return value.map((item) => {
      const raw = (item ?? {}) as Record<string, unknown>
      return {
        email: String(raw.email ?? raw.account_id ?? 'unknown'),
        requests: normalizeNumber(raw.requests),
        total_tokens: normalizeNumber(raw.total_tokens ?? raw.tokens)
      }
    })
  }

  const fetchSummary = async () => {
    loading.value = true
    error.value = ''
    try {
      const response = await apiGet<unknown>('/stats/summary')
      summary.value = normalizeSummary(response)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载统计汇总失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchHourly = async (date?: string) => {
    loading.value = true
    error.value = ''
    try {
      const query = date ? `?date=${encodeURIComponent(date)}` : ''
      const response = await apiGet<unknown>(`/stats/hourly${query}`)
      hourlyData.value = normalizeHourly(response)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载小时统计失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchDaily = async (days?: number) => {
    loading.value = true
    error.value = ''
    try {
      const query = days ? `?days=${days}` : ''
      const response = await apiGet<unknown>(`/stats/daily${query}`)
      dailyData.value = normalizeDaily(response)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载每日统计失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchModels = async () => {
    loading.value = true
    error.value = ''
    try {
      const response = await apiGet<unknown>('/stats/models')
      modelDist.value = normalizeModelDist(response)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载模型统计失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchAccountUsage = async () => {
    loading.value = true
    error.value = ''
    try {
      const response = await apiGet<unknown>('/stats/accounts')
      accountUsage.value = normalizeAccountUsage(response)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载账号用量失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    summary,
    hourlyData,
    dailyData,
    modelDist,
    accountUsage,
    loading,
    error,
    fetchSummary,
    fetchHourly,
    fetchDaily,
    fetchModels,
    fetchAccountUsage
  }
})
