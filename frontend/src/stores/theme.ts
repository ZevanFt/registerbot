import { defineStore } from 'pinia'
import { ref } from 'vue'

const THEME_DARK_KEY = 'theme-dark'

function readStoredTheme(): boolean | null {
  if (typeof window === 'undefined') {
    return null
  }

  const value = window.localStorage.getItem(THEME_DARK_KEY)
  if (value === 'true') {
    return true
  }
  if (value === 'false') {
    return false
  }
  return null
}

function prefersDark(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyThemeClass(isDark: boolean) {
  if (typeof document === 'undefined') {
    return
  }
  document.documentElement.classList.toggle('dark', isDark)
}

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref<boolean>(readStoredTheme() ?? false)

  const toggle = () => {
    isDark.value = !isDark.value
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_DARK_KEY, String(isDark.value))
    }
    applyThemeClass(isDark.value)
  }

  const init = () => {
    const stored = readStoredTheme()
    isDark.value = stored ?? prefersDark()

    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_DARK_KEY, String(isDark.value))
    }
    applyThemeClass(isDark.value)
  }

  return {
    isDark,
    toggle,
    init
  }
})
