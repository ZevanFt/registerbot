<template>
  <div class="space-y-[18px]">
    <section class="panel px-4 py-2">
      <div class="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
        <span class="h-2.5 w-2.5 rounded-full" :class="running ? 'bg-emerald-500' : 'bg-slate-400'" />
        <span>{{ running ? '注册服务器执行中' : '注册服务器待机' }}</span>
        <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-slate-700 dark:text-slate-300">
          {{ mode === 'http' ? 'HTTP' : 'BROWSER' }}
        </span>
        <span
          v-if="lastError"
          class="rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-600 dark:bg-rose-900/40 dark:text-rose-300"
        >
          最近一次失败
        </span>
      </div>
    </section>

    <section class="panel p-3.5">
      <div class="flex flex-wrap items-end gap-3">
        <label class="block">
          <span class="mb-1 block text-xs font-medium tracking-wide text-slate-500 dark:text-slate-300">注册类型</span>
          <select v-model="mode" class="field w-[112px]">
            <option value="http">HTTP</option>
            <option value="browser">BROWSER</option>
          </select>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium tracking-wide text-slate-500 dark:text-slate-300">数量</span>
          <input v-model.number="targetCount" min="1" class="field w-[90px]" type="number" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium tracking-wide text-slate-500 dark:text-slate-300">失败阈值</span>
          <input v-model.number="maxFailures" min="1" class="field w-[92px]" type="number" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium tracking-wide text-slate-500 dark:text-slate-300">间隔(s)</span>
          <input v-model.number="delaySeconds" min="0" step="0.5" class="field w-[88px]" type="number" />
        </label>

        <label v-if="mode === 'http'" class="block min-w-[260px] flex-1">
          <span class="mb-1 block text-xs font-medium tracking-wide text-slate-500 dark:text-slate-300">Turnstile Token (可选)</span>
          <input
            v-model="turnstileToken"
            class="field w-full"
            type="text"
            placeholder="为空时使用配置 registration.http_turnstile_token"
          />
        </label>

        <button
          type="button"
          class="ml-auto rounded-lg border px-4 py-2 text-sm font-semibold"
          :disabled="running"
          :class="
            running
              ? 'cursor-not-allowed border-slate-300 bg-slate-100 text-slate-400'
              : 'border-emerald-300 bg-emerald-50 text-emerald-700'
          "
          @click="startHttpTest"
        >
          {{ running ? '执行中...' : '开始测试' }}
        </button>
      </div>
      <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">
        成功注册将自动写入账号管理（`accounts` 表），可在下方尝试记录看到 `account_id`。
      </p>
      <p v-if="mode === 'http'" class="mt-1 text-xs text-slate-500 dark:text-slate-400">
        代理池: <span class="font-semibold">{{ proxyPoolEnabled ? '启用' : '未启用' }}</span>，规模: {{ proxyPoolSize }}
      </p>
    </section>

    <section v-if="mode === 'http'" class="panel p-4">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-slate-800 dark:text-slate-100">风控检测</h2>
        <button
          type="button"
          class="rounded-md border px-3 py-1.5 text-xs font-semibold"
          :disabled="riskLoading"
          :class="
            riskLoading
              ? 'cursor-not-allowed border-slate-300 bg-slate-100 text-slate-400'
              : 'border-sky-300 bg-sky-50 text-sky-700'
          "
          @click="runRiskProbe"
        >
          {{ riskLoading ? '检测中...' : '检测当前出口 IP' }}
        </button>
      </div>
      <div class="mt-3 grid gap-2 text-xs md:grid-cols-2">
        <p class="rounded-md bg-slate-100 px-2 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          状态码: <span class="font-semibold">{{ riskStatusCode ?? '-' }}</span>
        </p>
        <p class="rounded-md bg-slate-100 px-2 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          Challenge: <span class="font-semibold" :class="riskChallenge ? 'text-rose-600' : 'text-emerald-600'">{{ riskChallenge === null ? '-' : riskChallenge ? '是' : '否' }}</span>
        </p>
      </div>
      <p v-if="riskFinalUrl" class="mt-2 break-all text-xs text-slate-500 dark:text-slate-400">URL: {{ riskFinalUrl }}</p>
      <p v-if="riskMarkers.length > 0" class="mt-1 text-xs text-rose-600 dark:text-rose-300">
        markers: {{ riskMarkers.join(', ') }}
      </p>
      <p v-if="riskError" class="mt-2 rounded-md bg-rose-50 px-2.5 py-2 text-xs font-medium text-rose-600 dark:bg-rose-900/30 dark:text-rose-300">
        {{ riskError }}
      </p>
      <p v-if="riskSnippet" class="mt-2 max-h-24 overflow-auto rounded-md bg-slate-100 px-2 py-1 text-[11px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        {{ riskSnippet }}
      </p>
    </section>

    <section class="panel p-4">
      <div class="flex items-center justify-between text-sm font-semibold text-slate-700 dark:text-slate-200">
        <span>注册进度</span>
        <span class="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-700 dark:text-slate-300">{{ formatDuration(elapsedSeconds) }}</span>
      </div>
      <div class="mt-3 h-2.5 rounded-full bg-slate-200 dark:bg-slate-700">
        <div class="h-full rounded-full bg-emerald-500 transition-all" :style="{ width: `${progressPercent}%` }" />
      </div>
      <p class="mt-2 text-center text-xs font-medium tracking-wide text-slate-500 dark:text-slate-400">{{ progressCurrent }} / {{ targetCount }}</p>

      <div class="mt-3.5 grid gap-2.5 md:grid-cols-3">
        <article class="mini-card">
          <p class="stat-value text-emerald-600">{{ successCount }}</p>
          <p class="mt-1 text-xs font-medium tracking-wide text-slate-500">成功</p>
        </article>
        <article class="mini-card">
          <p class="stat-value text-slate-800 dark:text-slate-100">{{ failureCount }}</p>
          <p class="mt-1 text-xs font-medium tracking-wide text-slate-500">失败</p>
        </article>
        <article class="mini-card">
          <p class="stat-value text-amber-500">{{ uncertainCount }}</p>
          <p class="mt-1 text-xs font-medium tracking-wide text-slate-500">不确定</p>
        </article>
      </div>
      <p v-if="lastError" class="mt-3 rounded-md bg-rose-50 px-2.5 py-2 text-xs font-medium text-rose-600 dark:bg-rose-900/30 dark:text-rose-300">
        {{ lastError }}
      </p>
    </section>

    <section class="panel p-[18px]">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-slate-800 dark:text-slate-100">注册成功率监控</h2>
        <span class="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-900/30 dark:text-emerald-300">实时</span>
      </div>
      <div class="mt-4 space-y-3">
        <div v-for="stage in stageRows" :key="stage.key" class="grid grid-cols-[124px_1fr_76px_82px] items-center gap-3">
          <p class="text-sm font-medium text-slate-600 dark:text-slate-300">{{ stage.label }}</p>
          <div class="h-[22px] rounded-full bg-slate-200 p-0.5 dark:bg-slate-700">
            <div class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-green-400 transition-all" :style="{ width: `${stage.rate}%` }" />
          </div>
          <p class="text-right text-xs font-semibold text-slate-700 dark:text-slate-200">{{ stage.rate.toFixed(1) }}%</p>
          <p class="text-right text-xs font-medium text-slate-400 dark:text-slate-500">{{ stage.success }}/{{ stage.total }}</p>
        </div>
      </div>
      <div class="mt-4 border-t border-slate-200 pt-2.5 text-right dark:border-slate-700">
        <p class="text-xs font-medium tracking-wide text-slate-500">总成功率</p>
        <p class="text-[28px] font-semibold leading-none text-emerald-600">{{ overallRate.toFixed(1) }}% ({{ successCount }}/{{ progressCurrent || 1 }})</p>
      </div>
    </section>

    <section class="panel p-4">
      <div class="mb-2 flex items-center justify-between">
        <h2 class="text-base font-semibold text-slate-800 dark:text-slate-100">最近尝试与日志</h2>
        <button
          type="button"
          class="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
          @click="refreshLogs"
        >
          刷新日志
        </button>
      </div>

      <div class="grid gap-3 md:grid-cols-3">
        <article class="mini-card text-left">
          <p class="text-xs font-semibold tracking-wide text-slate-500">最近尝试</p>
          <div class="mt-2 max-h-44 overflow-auto rounded-md border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-800">
            <p v-if="attempts.length === 0" class="text-xs text-slate-500">暂无记录</p>
            <ul v-else class="space-y-1.5">
              <li v-for="item in attempts.slice().reverse().slice(0, 8)" :key="item.attempt" class="text-xs">
                <span class="font-medium text-slate-700 dark:text-slate-200">#{{ item.attempt }}</span>
                <span class="mx-1 text-slate-400">|</span>
                <span :class="item.success ? 'text-emerald-600' : 'text-rose-600'">{{ item.success ? '成功' : '失败' }}</span>
                <span class="mx-1 text-slate-400">|</span>
                <span class="text-slate-500">账号ID: {{ item.account_id ?? '-' }}</span>
                <span class="mx-1 text-slate-400">|</span>
                <span class="text-slate-500">代理: {{ item.proxy || '-' }}</span>
                <span
                  v-if="item.challenge_detected"
                  class="ml-1 rounded bg-rose-100 px-1 py-0.5 text-[10px] font-semibold text-rose-600 dark:bg-rose-900/40 dark:text-rose-300"
                >
                  challenge
                </span>
                <p v-if="!item.success" class="mt-0.5 line-clamp-2 text-[11px] text-rose-500">{{ firstError(item.errors) }}</p>
              </li>
            </ul>
          </div>
        </article>

        <article class="mini-card text-left">
          <p class="text-xs font-semibold tracking-wide text-slate-500">后端日志（devtools）</p>
          <div class="mt-2 flex items-center gap-2">
            <select v-model="selectedLogFile" class="field w-full text-sm" @change="refreshLogs">
              <option value="">选择日志文件</option>
              <option v-for="file in logFiles" :key="file" :value="file">{{ file }}</option>
            </select>
          </div>
          <div class="mt-2 max-h-44 overflow-auto rounded-md border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-800">
            <p v-if="logLines.length === 0" class="text-xs text-slate-500">暂无日志</p>
            <ul v-else class="space-y-1.5">
              <li v-for="line in logLines.slice().reverse().slice(0, 60)" :key="line.id" class="text-xs">
                <span class="font-semibold" :class="line.level === 'ERROR' ? 'text-rose-600' : 'text-slate-700 dark:text-slate-200'">{{ line.level }}</span>
                <span class="mx-1 text-slate-400">{{ formatTs(line.timestamp) }}</span>
                <span class="text-slate-500">{{ line.message }}</span>
              </li>
            </ul>
          </div>
        </article>

        <article class="mini-card text-left">
          <p class="text-xs font-semibold tracking-wide text-slate-500">代理池状态</p>
          <div class="mt-2 max-h-44 overflow-auto rounded-md border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-800">
            <p v-if="proxyStats.length === 0" class="text-xs text-slate-500">暂无代理统计</p>
            <ul v-else class="space-y-1.5">
              <li v-for="item in proxyStats" :key="item.proxy" class="text-xs">
                <p class="truncate font-medium text-slate-700 dark:text-slate-200">{{ item.proxy }}</p>
                <p class="text-slate-500">选中: {{ item.selected_count }} / 成功: {{ item.success_count }}</p>
                <p class="text-slate-400">冷却至: {{ item.cooldown_until ? formatTs(item.cooldown_until) : '-' }}</p>
              </li>
            </ul>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiGet, apiPost } from '@/api/client'

interface StageRow {
  key: string
  label: string
  success: number
  total: number
  rate: number
}

interface LogEntry {
  id: number | string
  timestamp: string
  level: string
  source: string
  message: string
}

interface HttpTestResponse {
  mode?: string
  attempts_total: number
  success_count: number
  failure_count: number
  proxy_pool_enabled?: boolean
  proxy_pool_size?: number
  proxy_stats?: Array<{ proxy: string; selected_count: number; success_count: number; cooldown_until: string | null }>
  stage_stats: Array<{ step: string; label: string; success: number; total: number; success_rate: number }>
  attempts: Array<{
    attempt: number
    email: string
    success: boolean
    account_id?: number
    proxy?: string
    challenge_detected?: boolean
    errors: Record<string, string>
  }>
}

interface RiskProbeResponse {
  status_code: number
  final_url: string
  challenge_detected: boolean
  markers: string[]
  body_snippet: string
}

const targetCount = ref(3)
const mode = ref<'http' | 'browser'>('http')
const maxFailures = ref(3)
const delaySeconds = ref(2)
const turnstileToken = ref('')
const running = ref(false)
const elapsedSeconds = ref(0)

const progressCurrent = ref(0)
const successCount = ref(0)
const failureCount = ref(0)
const uncertainCount = ref(0)
const stages = ref<Array<{ key: string; label: string; success: number; total: number }>>([])
const attempts = ref<HttpTestResponse['attempts']>([])
const lastError = ref('')
const logFiles = ref<string[]>([])
const selectedLogFile = ref('')
const logLines = ref<LogEntry[]>([])
const riskLoading = ref(false)
const riskStatusCode = ref<number | null>(null)
const riskFinalUrl = ref('')
const riskChallenge = ref<boolean | null>(null)
const riskMarkers = ref<string[]>([])
const riskSnippet = ref('')
const riskError = ref('')
const proxyPoolEnabled = ref(false)
const proxyPoolSize = ref(0)
const proxyStats = ref<Array<{ proxy: string; selected_count: number; success_count: number; cooldown_until: string | null }>>([])

let tickTimer: ReturnType<typeof setInterval> | null = null
let logPollTimer: ReturnType<typeof setInterval> | null = null

const progressPercent = computed(() => {
  if (targetCount.value <= 0) return 0
  return Math.min((progressCurrent.value / targetCount.value) * 100, 100)
})

const stageRows = computed<StageRow[]>(() =>
  stages.value.map((item) => ({
    ...item,
    rate: item.total > 0 ? (item.success / item.total) * 100 : 0,
  }))
)

const overallRate = computed(() => {
  if (progressCurrent.value <= 0) return 0
  return (successCount.value / progressCurrent.value) * 100
})

function formatDuration(totalSeconds: number): string {
  const mins = Math.floor(totalSeconds / 60)
  const secs = totalSeconds % 60
  return `${mins}m ${secs}s`
}

function startElapsedLoop() {
  if (tickTimer) return
  tickTimer = setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
}

function stopElapsedLoop() {
  if (!tickTimer) return
  clearInterval(tickTimer)
  tickTimer = null
}

function parseErrorMessage(err: unknown): string {
  if (!(err instanceof Error)) return '请求失败'
  const text = err.message || ''
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed?.detail === 'string') return parsed.detail
  } catch {
    return text
  }
  return text
}

function firstError(errors: Record<string, string> | undefined): string {
  if (!errors) return '未知错误'
  const first = Object.values(errors)[0]
  return first || '未知错误'
}

function formatTs(text: string): string {
  if (!text) return ''
  const dt = new Date(text)
  if (Number.isNaN(dt.getTime())) return text
  return dt.toLocaleTimeString()
}

async function loadLogFiles() {
  try {
    const response = await apiGet<{ files: string[] }>('/devtools/logs/files')
    logFiles.value = Array.isArray(response.files) ? response.files : []
    if (!selectedLogFile.value && logFiles.value.length > 0) {
      selectedLogFile.value = logFiles.value[0]
    }
  } catch (err) {
    lastError.value = parseErrorMessage(err)
  }
}

async function refreshLogs() {
  if (!selectedLogFile.value) {
    await loadLogFiles()
    if (!selectedLogFile.value) return
  }
  try {
    const query = new URLSearchParams({
      file: selectedLogFile.value,
      offset: '0',
      limit: '200',
    })
    const response = await apiGet<{ items: LogEntry[] }>(`/devtools/logs/history?${query.toString()}`)
    logLines.value = Array.isArray(response.items) ? response.items : []
  } catch (err) {
    lastError.value = parseErrorMessage(err)
  }
}

function startLogPolling() {
  if (logPollTimer) return
  logPollTimer = setInterval(() => {
    void refreshLogs()
  }, 2500)
}

function stopLogPolling() {
  if (!logPollTimer) return
  clearInterval(logPollTimer)
  logPollTimer = null
}

async function startHttpTest() {
  running.value = true
  elapsedSeconds.value = 0
  progressCurrent.value = 0
  successCount.value = 0
  failureCount.value = 0
  uncertainCount.value = 0
  attempts.value = []
  lastError.value = ''
  startElapsedLoop()
  startLogPolling()

  try {
    const response = await apiPost<HttpTestResponse>('/devtools/registration/test', {
      mode: mode.value,
      target: Math.max(1, targetCount.value),
      max_failures: Math.max(1, maxFailures.value),
      delay_seconds: Math.max(0, delaySeconds.value),
      turnstile_token: mode.value === 'http' ? turnstileToken.value.trim() : '',
    })

    attempts.value = response.attempts || []
    successCount.value = Number(response.success_count || 0)
    failureCount.value = Number(response.failure_count || 0)
    proxyPoolEnabled.value = mode.value === 'http' && Boolean(response.proxy_pool_enabled)
    proxyPoolSize.value = mode.value === 'http' ? Number(response.proxy_pool_size || 0) : 0
    proxyStats.value = mode.value === 'http' && Array.isArray(response.proxy_stats) ? response.proxy_stats : []
    progressCurrent.value = Number(response.attempts_total || 0)
    uncertainCount.value = Math.max(0, progressCurrent.value - successCount.value - failureCount.value)
    stages.value = (response.stage_stats || []).map((item) => ({
      key: item.step,
      label: item.label,
      success: Number(item.success || 0),
      total: Number(item.total || 0),
    }))

    const firstFailed = attempts.value.find((item) => !item.success)
    if (firstFailed) {
      lastError.value = firstError(firstFailed.errors)
    }
  } catch (err) {
    lastError.value = parseErrorMessage(err)
  } finally {
    running.value = false
    stopElapsedLoop()
    stopLogPolling()
    await refreshLogs()
  }
}

async function runRiskProbe() {
  riskLoading.value = true
  riskError.value = ''
  try {
    const response = await apiPost<RiskProbeResponse>('/devtools/registration/http-risk-probe', { authorize_url: '' })
    riskStatusCode.value = Number(response.status_code || 0)
    riskFinalUrl.value = response.final_url || ''
    riskChallenge.value = Boolean(response.challenge_detected)
    riskMarkers.value = Array.isArray(response.markers) ? response.markers : []
    riskSnippet.value = response.body_snippet || ''
  } catch (err) {
    riskError.value = parseErrorMessage(err)
  } finally {
    riskLoading.value = false
  }
}

onMounted(async () => {
  await loadLogFiles()
  await refreshLogs()
  await runRiskProbe()
})

onUnmounted(() => {
  stopElapsedLoop()
  stopLogPolling()
})
</script>

<style scoped>
.panel {
  border-radius: 0.75rem;
  border: 1px solid rgb(226 232 240);
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
}

.field {
  border-radius: 0.5rem;
  border: 1px solid rgb(203 213 225);
  padding: 0.45rem 0.65rem;
  font-size: 0.92rem;
  line-height: 1.15rem;
  color: rgb(51 65 85);
  font-weight: 500;
}

.mini-card {
  border-radius: 0.75rem;
  border: 1px solid rgb(226 232 240);
  background: rgb(248 250 252);
  padding: 0.7rem;
  text-align: center;
}

.stat-value {
  font-size: 1.75rem;
  line-height: 1;
  font-weight: 650;
}

.switch {
  width: 2.75rem;
  height: 1.5rem;
  border-radius: 999px;
  position: relative;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  padding: 0.125rem;
}

:global(.dark) .panel {
  border-color: rgb(51 65 85);
  background: rgb(30 41 59);
}

:global(.dark) .field {
  border-color: rgb(71 85 105);
  background: rgb(51 65 85);
  color: rgb(241 245 249);
}

:global(.dark) .mini-card {
  border-color: rgb(51 65 85);
  background: rgb(15 23 42);
}
</style>
