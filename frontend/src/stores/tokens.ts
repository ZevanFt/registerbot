import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiDelete, apiGet, apiPost } from '@/api/client'

export interface Token {
  id: number
  name: string
  key?: string
  created_at: string
  last_used_at: string | null
  is_active: boolean
  total_requests: number
  total_tokens: number
}

export const useTokensStore = defineStore('tokens', () => {
  const tokens = ref<Token[]>([])
  const loading = ref(false)
  const error = ref('')

  const fetchTokens = async (reveal = false) => {
    loading.value = true
    error.value = ''
    try {
      const query = reveal ? '?reveal=true' : ''
      tokens.value = await apiGet<Token[]>(`/tokens${query}`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载令牌失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createToken = async (name: string) => {
    loading.value = true
    error.value = ''
    try {
      const created = await apiPost<Token>('/tokens', { name })
      tokens.value = [created, ...tokens.value]
      return created
    } catch (err) {
      error.value = err instanceof Error ? err.message : '创建令牌失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const revokeToken = async (id: number) => {
    loading.value = true
    error.value = ''
    try {
      await apiDelete(`/tokens/${id}`)
      tokens.value = tokens.value.map((token) =>
        token.id === id
          ? {
              ...token,
              is_active: false
            }
          : token
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : '撤销令牌失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    tokens,
    loading,
    error,
    fetchTokens,
    createToken,
    revokeToken
  }
})
