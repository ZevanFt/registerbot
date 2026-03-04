import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiGet } from '@/api/client'

export interface AccountStats {
  total: number
  active: number
  cooling: number
  banned: number
  expired: number
  abandoned: number
}

export interface UsageStats {
  today_requests: number
  today_tokens: number
  current_rpm: number
}

export interface DashboardModel {
  id: string
  name: string
}

export interface ServiceStats {
  uptime_seconds: number
  python_version: string
}

export interface DashboardStats {
  accounts: AccountStats
  usage: UsageStats
  models: DashboardModel[]
  service: ServiceStats
}

const defaultStats: DashboardStats = {
  accounts: {
    total: 0,
    active: 0,
    cooling: 0,
    banned: 0,
    expired: 0,
    abandoned: 0
  },
  usage: {
    today_requests: 0,
    today_tokens: 0,
    current_rpm: 0
  },
  models: [],
  service: {
    uptime_seconds: 0,
    python_version: '-'
  }
}

export const useDashboardStore = defineStore('dashboard', () => {
  const stats = ref<DashboardStats>(defaultStats)
  const loading = ref(false)
  const error = ref('')

  const fetchStats = async () => {
    loading.value = true
    error.value = ''

    try {
      const response = await apiGet<DashboardStats>('/dashboard/stats')
      stats.value = response
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载仪表盘数据失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    stats,
    loading,
    error,
    fetchStats
  }
})
