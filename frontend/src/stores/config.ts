import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiGet, apiPut } from '@/api/client'

export interface AppConfig {
  admin: {
    username: string
    password: string
    jwt_secret: string
    jwt_expire_hours: number
  }
  openai: {
    base_url: string
    auth_url: string
    authorize_url: string
    token_url: string
    register_url: string
    register_callback_url: string
    oauth_client_id: string
    oauth_client_secret: string
    turnstile_sitekey: string
    default_password: string
    timeout_seconds: number
    stream_timeout_seconds: number
  }
  talentmail: {
    base_url: string
    email: string
    password: string
  }
  registration: {
    mode: 'browser' | 'http'
    skip_phone_verification: boolean
    skip_upgrade_plus: boolean
    profile_name: string
    max_concurrent_registrations: number
    headless: boolean
    browser_timeout: number
    typing_delay_ms: number
    navigation_timeout: number
  }
  proxy: {
    cooldown_seconds: number
    failure_threshold: number
    health_check_interval_seconds: number
    token_refresh_enabled: boolean
    token_refresh_interval_seconds: number
    token_refresh_skew_seconds: number
    token_refresh_timeout_seconds: number
    token_refresh_max_retries: number
    token_refresh_backoff_seconds: number
  }
  network: {
    http_proxy: string
    openai_proxy: string
    talentmail_proxy: string
  }
  storage: {
    db_path: string
    encryption_key: string
    tokens_db_path: string
    stats_db_path: string
  }
  logging: {
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
    format: 'json' | 'text'
  }
}

export const defaultConfig: AppConfig = {
  admin: {
    username: '',
    password: '',
    jwt_secret: '',
    jwt_expire_hours: 24
  },
  openai: {
    base_url: '',
    auth_url: '',
    authorize_url: '',
    token_url: '',
    register_url: '',
    register_callback_url: '',
    oauth_client_id: '',
    oauth_client_secret: '',
    turnstile_sitekey: '',
    default_password: '',
    timeout_seconds: 120,
    stream_timeout_seconds: 300
  },
  talentmail: {
    base_url: '',
    email: '',
    password: ''
  },
  registration: {
    mode: 'browser',
    skip_phone_verification: true,
    skip_upgrade_plus: true,
    profile_name: '',
    max_concurrent_registrations: 1,
    headless: true,
    browser_timeout: 30,
    typing_delay_ms: 150,
    navigation_timeout: 60
  },
  proxy: {
    cooldown_seconds: 60,
    failure_threshold: 3,
    health_check_interval_seconds: 30,
    token_refresh_enabled: true,
    token_refresh_interval_seconds: 30,
    token_refresh_skew_seconds: 300,
    token_refresh_timeout_seconds: 15,
    token_refresh_max_retries: 3,
    token_refresh_backoff_seconds: 60
  },
  network: {
    http_proxy: '',
    openai_proxy: '',
    talentmail_proxy: ''
  },
  storage: {
    db_path: '',
    encryption_key: '',
    tokens_db_path: '',
    stats_db_path: ''
  },
  logging: {
    level: 'INFO',
    format: 'json'
  }
}

export const useConfigStore = defineStore('config', () => {
  const config = ref<AppConfig>(structuredClone(defaultConfig))
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')

  const fetchConfig = async () => {
    loading.value = true
    error.value = ''
    try {
      const raw = await apiGet<Record<string, unknown>>('/config')
      const merged = structuredClone(defaultConfig) as unknown as Record<string, unknown>
      for (const section of Object.keys(merged)) {
        if (raw[section] && typeof raw[section] === 'object') {
          merged[section] = { ...(merged[section] as unknown as Record<string, unknown>), ...(raw[section] as unknown as Record<string, unknown>) }
        }
      }
      config.value = merged as unknown as AppConfig
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载配置失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const saveConfig = async (data: AppConfig) => {
    saving.value = true
    error.value = ''
    try {
      const raw = await apiPut<Record<string, unknown>>('/config', data)
      const merged = structuredClone(defaultConfig) as unknown as Record<string, unknown>
      for (const section of Object.keys(merged)) {
        if (raw[section] && typeof raw[section] === 'object') {
          merged[section] = { ...(merged[section] as unknown as Record<string, unknown>), ...(raw[section] as unknown as Record<string, unknown>) }
        }
      }
      config.value = merged as unknown as AppConfig
      return config.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '保存配置失败'
      throw err
    } finally {
      saving.value = false
    }
  }

  return {
    config,
    loading,
    saving,
    error,
    fetchConfig,
    saveConfig
  }
})
