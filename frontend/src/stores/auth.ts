import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { apiGet, apiPost } from '@/api/client'

const TOKEN_KEY = 'admin_token'
const USERNAME_KEY = 'admin_username'

interface LoginResponse {
  token: string
  username: string
}

interface MeResponse {
  username: string
}

function getStoredValue(key: string): string {
  if (typeof window === 'undefined') {
    return ''
  }
  return window.localStorage.getItem(key) ?? ''
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getStoredValue(TOKEN_KEY))
  const username = ref<string>(getStoredValue(USERNAME_KEY))
  const loading = ref(false)
  const error = ref('')
  const isLoggedIn = computed(() => !!token.value)

  const persist = () => {
    if (typeof window === 'undefined') {
      return
    }
    if (token.value) {
      window.localStorage.setItem(TOKEN_KEY, token.value)
    } else {
      window.localStorage.removeItem(TOKEN_KEY)
    }
    if (username.value) {
      window.localStorage.setItem(USERNAME_KEY, username.value)
    } else {
      window.localStorage.removeItem(USERNAME_KEY)
    }
  }

  const login = async (inputUsername: string, password: string) => {
    loading.value = true
    error.value = ''
    try {
      const result = await apiPost<LoginResponse>('/auth/login', { username: inputUsername, password })
      token.value = result.token
      username.value = result.username
      persist()
      return result
    } catch (err) {
      error.value = err instanceof Error ? err.message : '登录失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    token.value = ''
    username.value = ''
    error.value = ''
    persist()
    if (typeof window !== 'undefined' && window.location.hash !== '#/login') {
      window.location.hash = '#/login'
    }
  }

  const checkAuth = async () => {
    if (!token.value) {
      return false
    }

    loading.value = true
    error.value = ''
    try {
      const profile = await apiGet<MeResponse>('/auth/me')
      username.value = profile.username
      persist()
      return true
    } catch (err) {
      logout()
      error.value = err instanceof Error ? err.message : '认证已失效'
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    token,
    username,
    loading,
    error,
    isLoggedIn,
    login,
    logout,
    checkAuth
  }
})
