import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'

export type AccountStatus = 'active' | 'cooling' | 'banned' | 'expired' | 'pending' | 'abandoned'

export interface Account {
  id: number
  email: string
  plan: 'free' | 'plus'
  status: AccountStatus
  runtime_status: string | null
  token_status: string | null
  consecutive_failures: number
  last_failure_reason: string | null
  created_at: string
  updated_at: string
}

export interface AccountExportPayload {
  exported_at: string
  count: number
  accounts: Array<Record<string, unknown>>
}

export interface AccountImportPayload {
  conflict_strategy: 'skip' | 'overwrite'
  accounts: Array<Record<string, unknown>>
}

export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref<Account[]>([])
  const loading = ref(false)
  const error = ref('')

  const fetchAccounts = async () => {
    loading.value = true
    error.value = ''
    try {
      accounts.value = await apiGet<Account[]>('/accounts')
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载账号失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const updateAccountStatus = async (id: number, status: AccountStatus) => {
    loading.value = true
    error.value = ''
    try {
      const updated = await apiPatch<Account>(`/accounts/${id}`, { status })
      accounts.value = accounts.value.map((account) => (account.id === id ? updated : account))
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : '更新账号状态失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const deleteAccount = async (id: number) => {
    loading.value = true
    error.value = ''
    try {
      await apiDelete(`/accounts/${id}`)
      accounts.value = accounts.value.filter((account) => account.id !== id)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '删除账号失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const revealAccountPassword = async (id: number) => {
    loading.value = true
    error.value = ''
    try {
      return await apiGet<{ id: number; email: string; password: string }>(`/accounts/${id}/password/reveal`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '查看密码失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const exportAccounts = async (ids: number[]) => {
    loading.value = true
    error.value = ''
    try {
      const query = ids.length > 0 ? `?ids=${ids.join(',')}` : ''
      return await apiGet<AccountExportPayload>(`/accounts/export${query}`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '导出账号失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const importAccounts = async (payload: AccountImportPayload) => {
    loading.value = true
    error.value = ''
    try {
      const result = await apiPost<{
        total: number
        imported: number
        updated: number
        skipped: number
        failed: number
        errors: Array<{ email: string; error: string }>
      }>('/accounts/import', payload)
      await fetchAccounts()
      return result
    } catch (err) {
      error.value = err instanceof Error ? err.message : '导入账号失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    accounts,
    loading,
    error,
    fetchAccounts,
    updateAccountStatus,
    deleteAccount,
    revealAccountPassword,
    exportAccounts,
    importAccounts
  }
})
