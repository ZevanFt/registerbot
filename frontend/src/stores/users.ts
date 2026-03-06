import { ref } from 'vue'
import { defineStore } from 'pinia'
import { apiGet, apiPatch, apiPost } from '@/api/client'

export type UserPermission = 'admin' | 'operator' | 'viewer'

export interface UserItem {
  id: number
  username: string
  email: string | null
  permission: UserPermission
  is_active: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
}

export interface CreateUserPayload {
  username: string
  password: string
  permission: UserPermission
  email?: string | null
  is_active: boolean
}

export const useUsersStore = defineStore('users', () => {
  const users = ref<UserItem[]>([])
  const loading = ref(false)
  const error = ref('')

  const fetchUsers = async () => {
    loading.value = true
    error.value = ''
    try {
      users.value = await apiGet<UserItem[]>('/users')
      return users.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取用户列表失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createUser = async (payload: CreateUserPayload) => {
    loading.value = true
    error.value = ''
    try {
      const created = await apiPost<UserItem>('/users', payload)
      users.value = [created, ...users.value]
      return created
    } catch (err) {
      error.value = err instanceof Error ? err.message : '创建用户失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const patchUser = async (
    id: number,
    payload: { permission?: UserPermission; email?: string | null; is_active?: boolean }
  ) => {
    loading.value = true
    error.value = ''
    try {
      const updated = await apiPatch<UserItem>(`/users/${id}`, payload)
      users.value = users.value.map((item) => (item.id === id ? updated : item))
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : '更新用户失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const resetPassword = async (id: number) => {
    loading.value = true
    error.value = ''
    try {
      return await apiPost<{ id: number; username: string; permission: UserPermission; new_password: string }>(
        `/users/${id}/reset-password`,
        {}
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : '重置密码失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    users,
    loading,
    error,
    fetchUsers,
    createUser,
    patchUser,
    resetPassword
  }
})
