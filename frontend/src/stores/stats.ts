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

  const fetchSummary = async () => {
    loading.value = true
    error.value = ''
    try {
      summary.value = await apiGet<StatsSummary>('/stats/summary')
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
      hourlyData.value = await apiGet<HourlyItem[]>(`/stats/hourly${query}`)
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
      dailyData.value = await apiGet<DailyItem[]>(`/stats/daily${query}`)
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
      modelDist.value = await apiGet<ModelDistributionItem[]>('/stats/models')
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
      accountUsage.value = await apiGet<AccountUsageItem[]>('/stats/accounts')
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
