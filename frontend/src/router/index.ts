import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { useAuthStore } from '@/stores/auth'

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
        meta: { title: '仪表盘' }
      },
      {
        path: 'accounts',
        name: 'accounts',
        component: () => import('@/pages/Accounts.vue'),
        meta: { title: '账号管理' }
      },
      {
        path: 'config',
        name: 'config',
        component: () => import('@/pages/Config.vue'),
        meta: { title: '配置' }
      },
      {
        path: 'tokens',
        name: 'tokens',
        component: () => import('@/pages/Tokens.vue'),
        meta: { title: '令牌管理' }
      },
      {
        path: 'stats',
        name: 'stats',
        component: () => import('@/pages/Stats.vue'),
        meta: { title: '统计' }
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('@/pages/Logs.vue'),
        meta: { title: '日志' }
      },
      {
        path: 'dev/logs',
        name: 'dev-logs',
        component: () => import('@/pages/DevLogs.vue'),
        meta: { title: '实时日志' }
      },
      {
        path: 'dev/pipeline',
        name: 'dev-pipeline',
        component: () => import('@/pages/DevPipeline.vue'),
        meta: { title: '流水线' }
      },
      {
        path: 'dev/test',
        name: 'dev-test',
        component: () => import('@/pages/DevTest.vue'),
        meta: { title: '测试面板' }
      },
      {
        path: 'playground',
        name: 'playground',
        component: () => import('@/pages/Playground.vue'),
        meta: { title: '操练场' }
      },
      {
        path: 'about',
        name: 'about',
        component: () => import('@/pages/About.vue'),
        meta: { title: '关于' }
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
  return true
})

export default router
