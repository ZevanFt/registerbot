import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'

export type AccountStatus = 'active' | 'cooling' | 'banned' | 'expired' | 'pending' | 'abandoned'

export interface Account {
  id: number
  email: string
  plan: 'free' | 'plus'
  status: AccountStatus
  created_at: string
  updated_at: string
}

export interface CreateAccountPayload {
  email: string
  password: string
  plan: 'free' | 'plus'
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

  const createAccount = async (data: CreateAccountPayload) => {
    loading.value = true
    error.value = ''
    try {
      const created = await apiPost<Account>('/accounts', data)
      accounts.value = [created, ...accounts.value]
      return created
    } catch (err) {
      error.value = err instanceof Error ? err.message : '创建账号失败'
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

  return {
    accounts,
    loading,
    error,
    fetchAccounts,
    createAccount,
    updateAccountStatus,
    deleteAccount
  }
})
