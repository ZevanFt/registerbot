<template>
  <div class="flex h-screen overflow-hidden bg-slate-100 text-slate-800 dark:bg-slate-900 dark:text-slate-200">
    <aside
      class="sidebar-scroll h-screen shrink-0 overflow-y-auto border-r border-slate-200 bg-white transition-all duration-300 dark:border-slate-700 dark:bg-slate-800"
      :style="{ width: sidebarWidth }"
    >
      <div class="flex h-full flex-col">
        <div class="flex items-center gap-3 px-4 py-6">
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-cyan-400 text-sm font-bold text-white"
          >
            C
          </div>
          <span
            class="overflow-hidden whitespace-nowrap text-base font-semibold tracking-tight transition-all duration-300"
            :class="collapsed ? 'max-w-0 opacity-0' : 'max-w-[140px] opacity-100'"
          >
            codex2api
          </span>
        </div>

        <nav class="px-2">
          <template v-for="entry in visibleMenuEntries" :key="entry.key">
            <div
              v-if="entry.type === 'separator'"
              class="my-2 border-t border-slate-200 dark:border-slate-700"
              :class="collapsed ? 'mx-2' : 'mx-3'"
            />
            <p
              v-else-if="entry.type === 'label'"
              class="px-3 py-1 text-xs font-semibold tracking-wide text-slate-400 transition-all dark:text-slate-500"
              :class="collapsed ? 'max-h-0 overflow-hidden opacity-0' : 'max-h-8 opacity-100'"
            >
              {{ entry.label }}
            </p>
            <RouterLink
              v-else
              :to="entry.path"
              :title="collapsed ? entry.label : ''"
              class="mb-1 flex rounded-r-lg border-l-[3px] px-3 py-2.5 text-sm font-medium text-slate-600 transition"
              :class="[
                collapsed ? 'justify-center' : 'items-center gap-3',
                isActive(entry.path)
                  ? 'border-l-violet-500 bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300'
                  : 'border-l-transparent hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700'
              ]"
            >
              <span class="h-5 w-5 shrink-0" v-html="entry.icon" />
              <span
                class="overflow-hidden whitespace-nowrap transition-all duration-300"
                :class="collapsed ? 'max-w-0 opacity-0' : 'max-w-[120px] opacity-100'"
              >
                {{ entry.label }}
              </span>
            </RouterLink>
          </template>
        </nav>

        <div class="mt-auto flex items-center justify-between gap-2 px-3 py-4">
          <span
            class="overflow-hidden whitespace-nowrap text-xs text-slate-400 transition-all duration-300 dark:text-slate-500"
            :class="collapsed ? 'max-w-0 opacity-0' : 'max-w-[96px] opacity-100'"
          >
            codex2api
          </span>
          <button
            type="button"
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-slate-200 text-slate-500 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            :aria-label="collapsed ? '展开侧边栏' : '折叠侧边栏'"
            @click="toggleSidebar"
          >
            <svg v-if="collapsed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
              <polyline stroke-linecap="round" stroke-linejoin="round" points="9 18 15 12 9 6" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
              <polyline stroke-linecap="round" stroke-linejoin="round" points="15 18 9 12 15 6" />
            </svg>
          </button>
        </div>
      </div>
    </aside>

    <div class="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
      <header
        class="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-7 dark:border-slate-700 dark:bg-slate-800"
      >
        <h1 class="text-lg font-semibold">{{ pageTitle }}</h1>

        <div class="flex items-center gap-4">
          <button
            class="rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            中
          </button>
          <button
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-slate-500 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            aria-label="切换深色模式"
            @click="themeStore.toggle"
          >
            <svg
              v-if="themeStore.isDark"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              class="h-5 w-5"
            >
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-5 w-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" />
            </svg>
          </button>
          <div class="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <span class="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span>{{ authStore.username || 'admin' }}</span>
          </div>
          <button
            class="rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            @click="handleLogout"
          >
            退出登录
          </button>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

interface MenuLinkItem {
  type: 'item'
  path: string
  label: string
  icon: string
  key: string
  minPermission: 'viewer' | 'operator' | 'admin'
}

interface MenuLabelItem {
  type: 'label'
  label: string
  key: string
}

interface MenuSeparatorItem {
  type: 'separator'
  key: string
}

type MenuEntry = MenuLinkItem | MenuLabelItem | MenuSeparatorItem

const SIDEBAR_COLLAPSED_KEY = 'sidebar-collapsed'
const route = useRoute()
const themeStore = useThemeStore()
const authStore = useAuthStore()

const menuEntries: MenuEntry[] = [
  {
    type: 'item',
    key: 'dashboard',
    path: '/dashboard',
    label: '仪表盘',
    minPermission: 'viewer',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13h8V3H3v10zM13 21h8V11h-8v10zM13 3v4h8V3h-8zM3 21h8v-4H3v4z"/></svg>'
  },
  {
    type: 'item',
    key: 'accounts',
    path: '/accounts',
    label: '账号管理',
    minPermission: 'operator',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path stroke-linecap="round" stroke-linejoin="round" d="M23 21v-2a4 4 0 0 0-3-3.87"/><path stroke-linecap="round" stroke-linejoin="round" d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
  },
  {
    type: 'item',
    key: 'users',
    path: '/users',
    label: '用户管理',
    minPermission: 'admin',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path stroke-linecap="round" stroke-linejoin="round" d="M20 8v6"/><path stroke-linecap="round" stroke-linejoin="round" d="M17 11h6"/></svg>'
  },
  {
    type: 'item',
    key: 'tokens',
    path: '/tokens',
    label: '令牌管理',
    minPermission: 'operator',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path stroke-linecap="round" stroke-linejoin="round" d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>'
  },
  {
    type: 'item',
    key: 'playground',
    path: '/playground',
    label: '操练场',
    minPermission: 'operator',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
  },
  {
    type: 'item',
    key: 'stats',
    path: '/stats',
    label: '统计',
    minPermission: 'viewer',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
  },
  {
    type: 'item',
    key: 'logs',
    path: '/logs',
    label: '日志',
    minPermission: 'viewer',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline stroke-linecap="round" stroke-linejoin="round" points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline stroke-linecap="round" stroke-linejoin="round" points="10 9 9 9 8 9"/></svg>'
  },
  {
    type: 'item',
    key: 'config',
    path: '/config',
    label: '配置',
    minPermission: 'admin',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path stroke-linecap="round" stroke-linejoin="round" d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0A1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0A1.65 1.65 0 0 0 20.91 10H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
  },
  {
    type: 'item',
    key: 'dev-logs',
    path: '/dev/logs',
    label: '实时日志',
    minPermission: 'admin',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline stroke-linecap="round" stroke-linejoin="round" points="4 17 10 11 14 15 20 9"/><line x1="20" y1="9" x2="20" y2="15"/><line x1="20" y1="9" x2="14" y2="9"/><rect x="3" y="3" width="18" height="18" rx="2"/></svg>'
  },
  {
    type: 'item',
    key: 'dev-pipeline',
    path: '/dev/pipeline',
    label: '流水线',
    minPermission: 'admin',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="6" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="12" cy="18" r="2"/><line x1="7" y1="11" x2="10" y2="7"/><line x1="14" y1="7" x2="17" y2="11"/><line x1="17" y1="13" x2="14" y2="17"/><line x1="10" y1="17" x2="7" y2="13"/></svg>'
  },
  {
    type: 'item',
    key: 'dev-test',
    path: '/dev/test',
    label: '测试面板',
    minPermission: 'admin',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline stroke-linecap="round" stroke-linejoin="round" points="9 11 12 14 22 4"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>'
  },
  {
    type: 'separator',
    key: 'devtools-separator'
  },
  {
    type: 'label',
    key: 'devtools-label',
    label: '开发工具'
  },
  {
    type: 'item',
    key: 'registration-server',
    path: '/registration-server',
    label: '注册服务器',
    minPermission: 'admin',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="6" rx="1"/><rect x="3" y="14" width="18" height="6" rx="1"/><line x1="7" y1="7" x2="7.01" y2="7"/><line x1="7" y1="17" x2="7.01" y2="17"/></svg>'
  },
  {
    type: 'item',
    key: 'model-truth-probe',
    path: '/model-truth-probe',
    label: '模型真值探测',
    minPermission: 'admin',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3h6l1 4h4l-1 4-3 3 1 7-5-3-5 3 1-7-3-3-1-4h4z"/></svg>'
  },
  {
    type: 'separator',
    key: 'about-separator'
  },
  {
    type: 'item',
    key: 'about',
    path: '/about',
    label: '关于',
    minPermission: 'viewer',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  }
]

const collapsed = ref<boolean>(false)

if (typeof window !== 'undefined') {
  collapsed.value = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
}

watch(
  collapsed,
  (value) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(value))
    }
  },
  { immediate: true }
)

const sidebarWidth = computed(() => (collapsed.value ? '64px' : '208px'))
const pageTitle = computed(() => (route.meta.title as string) ?? '仪表盘')
const isActive = (path: string) => route.path === path
const permissionLevels = { viewer: 1, operator: 2, admin: 3 } as const
const devtoolsKeys = new Set(['dev-logs', 'dev-pipeline', 'dev-test', 'registration-server', 'model-truth-probe'])
const visibleMenuEntries = computed(() => {
  const currentPermission = (authStore.permission || 'viewer') as 'viewer' | 'operator' | 'admin'
  const currentLevel = permissionLevels[currentPermission] ?? 1
  const visibleItems = menuEntries
    .filter((entry): entry is MenuLinkItem => entry.type === 'item')
    .filter((entry) => currentLevel >= (permissionLevels[entry.minPermission] ?? 1))

  const normalItems = visibleItems.filter((entry) => !devtoolsKeys.has(entry.key))
  const devItems = visibleItems.filter((entry) => devtoolsKeys.has(entry.key))
  const merged: MenuEntry[] = [...normalItems]
  if (devItems.length > 0) {
    merged.push({ type: 'separator', key: 'devtools-separator-visible' })
    merged.push({ type: 'label', key: 'devtools-label-visible', label: '开发工具' })
    merged.push(...devItems)
  }
  return merged
})

function toggleSidebar() {
  collapsed.value = !collapsed.value
}

function handleLogout() {
  authStore.logout()
}
</script>
