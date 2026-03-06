<template>
  <div class="space-y-4">
    <p
      v-if="pageError || store.error"
      class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-300"
    >
      {{ pageError || store.error }}
    </p>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-100">Pipeline 可视化</h2>
          <p class="text-sm text-slate-500 dark:text-slate-400">实时追踪注册流水线执行状态</p>
        </div>
        <button
          type="button"
          class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          :disabled="triggering"
          @click="triggerRegister"
        >
          {{ triggering ? '触发中...' : '触发注册' }}
        </button>
      </div>

      <div class="mt-5 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
        <span class="h-2.5 w-2.5 rounded-full" :class="store.pipelineConnected ? 'bg-emerald-500' : 'bg-rose-500'" />
        <span>{{ store.pipelineConnected ? 'WebSocket 已连接' : 'WebSocket 未连接' }}</span>
      </div>

      <div class="mt-5 flex flex-col gap-4 xl:flex-row xl:items-stretch xl:gap-0">
        <template v-for="(step, index) in stepCards" :key="step.key">
          <article
            class="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900/60"
          >
            <div class="flex items-start justify-between gap-2">
              <h3 class="text-sm font-semibold text-slate-800 dark:text-slate-100">{{ index + 1 }}. {{ step.label }}</h3>
              <div class="shrink-0" :class="statusTextClass(step.status)">
                <svg
                  v-if="step.status === 'running'"
                  viewBox="0 0 24 24"
                  class="h-5 w-5 animate-spin"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path stroke-linecap="round" d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                <svg
                  v-else-if="step.status === 'success'"
                  viewBox="0 0 24 24"
                  class="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <polyline stroke-linecap="round" stroke-linejoin="round" points="20 6 9 17 4 12" />
                </svg>
                <svg
                  v-else-if="step.status === 'failed'"
                  viewBox="0 0 24 24"
                  class="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <line stroke-linecap="round" x1="18" y1="6" x2="6" y2="18" />
                  <line stroke-linecap="round" x1="6" y1="6" x2="18" y2="18" />
                </svg>
                <span v-else class="inline-block h-3 w-3 rounded-full border border-current" />
              </div>
            </div>
            <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">{{ step.key }}</p>
            <p class="mt-2 text-xs font-medium" :class="statusTextClass(step.status)">
              {{ statusLabel(step.status) }}
            </p>
            <p class="mt-2 text-xs tabular-nums text-slate-600 dark:text-slate-300">耗时: {{ formatDuration(step) }}</p>
            <p v-if="step.error" class="mt-2 text-xs text-rose-600 dark:text-rose-400">{{ step.error }}</p>
          </article>
          <div
            v-if="index < stepCards.length - 1"
            class="mx-2 hidden xl:flex xl:items-center xl:text-slate-400 dark:xl:text-slate-500"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="4" y1="12" x2="20" y2="12" />
              <polyline stroke-linecap="round" stroke-linejoin="round" points="14 6 20 12 14 18" />
            </svg>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiPost } from '@/api/client'
import { useDevtoolsStore, type PipelineEvent } from '@/stores/devtools'

type StepStatus = 'pending' | 'running' | 'success' | 'failed'

interface StepCard {
  key: string
  label: string
  status: StepStatus
  durationMs: number
  error: string
  timestamp: string
}

const store = useDevtoolsStore()
const tickingMs = ref(Date.now())
const triggering = ref(false)
const pageError = ref('')
const timer = setInterval(() => {
  tickingMs.value = Date.now()
}, 500)

const STEP_LABELS: Record<string, string> = {
  create_temp_email: '创建邮箱',
  browser_signup: '浏览器注册',
  wait_for_verification_code: '等待验证码',
  browser_verify_email: '验证邮箱',
  verify_phone: '电话验证',
  set_password: '获取令牌',
  set_profile: '设置资料',
  upgrade_plus: '升级 Plus'
}

const STEP_KEYS = Object.keys(STEP_LABELS)

const latestEventByStep = computed(() => {
  const map = new Map<string, PipelineEvent>()
  const events = Array.isArray(store.pipelineEvents) ? store.pipelineEvents : []
  for (const event of events) {
    map.set(event.step_name, event)
  }
  return map
})

const stepCards = computed<StepCard[]>(() => {
  return STEP_KEYS.map((key) => {
    const event = latestEventByStep.value.get(key)
    if (!event) {
      return {
        key,
        label: STEP_LABELS[key],
        status: 'pending',
        durationMs: 0,
        error: '',
        timestamp: ''
      }
    }

    const status = normalizeStatus(event.status)
    const baseDuration = event.duration_ms ?? 0
    const dynamicDuration =
      status === 'running' && event.timestamp
        ? Math.max(tickingMs.value - new Date(event.timestamp).getTime(), 0)
        : baseDuration

    return {
      key,
      label: STEP_LABELS[key],
      status,
      durationMs: dynamicDuration,
      error: event.error ?? '',
      timestamp: event.timestamp ?? ''
    }
  })
})

function normalizeStatus(status: string): StepStatus {
  const normalized = status.toLowerCase()
  if (normalized === 'running') {
    return 'running'
  }
  if (normalized === 'success' || normalized === 'done' || normalized === 'completed') {
    return 'success'
  }
  if (normalized === 'failed' || normalized === 'error') {
    return 'failed'
  }
  return 'pending'
}

function statusLabel(status: StepStatus): string {
  if (status === 'running') {
    return '执行中'
  }
  if (status === 'success') {
    return '成功'
  }
  if (status === 'failed') {
    return '失败'
  }
  return '等待'
}

function statusTextClass(status: StepStatus): string {
  if (status === 'running') {
    return 'text-blue-600 dark:text-blue-400'
  }
  if (status === 'success') {
    return 'text-emerald-600 dark:text-emerald-400'
  }
  if (status === 'failed') {
    return 'text-rose-600 dark:text-rose-400'
  }
  return 'text-slate-400 dark:text-slate-500'
}

function formatDuration(step: StepCard): string {
  if (!step.durationMs || step.durationMs < 0) {
    return '-'
  }
  if (step.durationMs < 1000) {
    return `${step.durationMs}ms`
  }
  return `${(step.durationMs / 1000).toFixed(2)}s`
}

async function triggerRegister() {
  triggering.value = true
  pageError.value = ''
  try {
    await apiPost('/pipeline/register', {})
  } catch (err) {
    pageError.value = err instanceof Error ? err.message : '触发流水线失败'
  } finally {
    triggering.value = false
  }
}

onMounted(async () => {
  try {
    await store.fetchLastPipelineEvents()
  } catch {
    // Error is reflected by store.error.
  }
  store.connectPipelineWs()
})

onUnmounted(() => {
  clearInterval(timer)
  store.disconnectPipelineWs()
})
</script>
