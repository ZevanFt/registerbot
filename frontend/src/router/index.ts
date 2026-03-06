import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { useAuthStore } from '@/stores/auth'

type Permission = 'viewer' | 'operator' | 'admin'

const permissionLevels: Record<Permission, number> = {
  viewer: 1,
  operator: 2,
  admin: 3
}

function hasPermission(actual: string, required: Permission): boolean {
  const actualLevel = permissionLevels[(actual as Permission) || 'viewer'] ?? 0
  const requiredLevel = permissionLevels[required] ?? 0
  return actualLevel >= requiredLevel
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: AdminLayout,
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/pages/Dashboard.vue'),
        meta: { title: '仪表盘', minPermission: 'viewer' }
      },
      {
        path: 'accounts',
        name: 'accounts',
        component: () => import('@/pages/Accounts.vue'),
        meta: { title: '账号管理', minPermission: 'operator' }
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/pages/Users.vue'),
        meta: { title: '用户管理', minPermission: 'admin' }
      },
      {
        path: 'config',
        name: 'config',
        component: () => import('@/pages/Config.vue'),
        meta: { title: '配置', minPermission: 'admin' }
      },
      {
        path: 'tokens',
        name: 'tokens',
        component: () => import('@/pages/Tokens.vue'),
        meta: { title: '令牌管理', minPermission: 'operator' }
      },
      {
        path: 'stats',
        name: 'stats',
        component: () => import('@/pages/Stats.vue'),
        meta: { title: '统计', minPermission: 'viewer' }
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('@/pages/Logs.vue'),
        meta: { title: '日志', minPermission: 'viewer' }
      },
      {
        path: 'dev/logs',
        name: 'dev-logs',
        component: () => import('@/pages/DevLogs.vue'),
        meta: { title: '实时日志', minPermission: 'operator' }
      },
      {
        path: 'dev/pipeline',
        name: 'dev-pipeline',
        component: () => import('@/pages/DevPipeline.vue'),
        meta: { title: '流水线', minPermission: 'operator' }
      },
      {
        path: 'dev/test',
        name: 'dev-test',
        component: () => import('@/pages/DevTest.vue'),
        meta: { title: '测试面板', minPermission: 'operator' }
      },
      {
        path: 'playground',
        name: 'playground',
        component: () => import('@/pages/Playground.vue'),
        meta: { title: '操练场', minPermission: 'operator' }
      },
      {
        path: 'about',
        name: 'about',
        component: () => import('@/pages/About.vue'),
        meta: { title: '关于', minPermission: 'viewer' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach(async (to) => {
  if (to.path === '/login') {
    return true
  }

  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) {
    return '/login'
  }

  if (!authStore.username) {
    const isValid = await authStore.checkAuth()
    if (!isValid) {
      return '/login'
    }
  }
  const required = (to.meta.minPermission as Permission | undefined) ?? 'viewer'
  if (!hasPermission(authStore.permission || 'viewer', required)) {
    return '/dashboard'
  }
  return true
})

router.onError((err) => {
  // Keep app navigable when a route/component throws during navigation.
  // The global error boundary in App.vue will display the actual error.
  // eslint-disable-next-line no-console
  console.error('[router-error]', err)
  if (typeof window !== 'undefined') {
    window.location.hash = '#/dashboard'
  }
})

export default router
