<template>
  <div class="space-y-4">
    <p
      v-if="store.error"
      class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-300"
    >
      {{ store.error }}
    </p>

    <section class="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="mb-3 flex items-center justify-between">
        <div class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1 dark:border-slate-600 dark:bg-slate-700">
          <button
            type="button"
            class="rounded-md px-3 py-1.5 text-sm transition"
            :class="
              activeTab === 'realtime'
                ? 'bg-white text-blue-700 shadow-sm dark:bg-slate-800 dark:text-blue-300'
                : 'text-slate-600 hover:text-slate-800 dark:text-slate-300 dark:hover:text-slate-100'
            "
            @click="activeTab = 'realtime'"
          >
            实时日志
          </button>
          <button
            type="button"
            class="rounded-md px-3 py-1.5 text-sm transition"
            :class="
              activeTab === 'history'
                ? 'bg-white text-blue-700 shadow-sm dark:bg-slate-800 dark:text-blue-300'
                : 'text-slate-600 hover:text-slate-800 dark:text-slate-300 dark:hover:text-slate-100'
            "
            @click="activeTab = 'history'"
          >
            历史日志
          </button>
        </div>
      </div>

      <div v-if="activeTab === 'realtime'" class="space-y-3">
        <div class="flex flex-col gap-2 lg:flex-row lg:items-center">
          <select
            v-model="store.logsFilter.level"
            class="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
          >
            <option value="ALL">全部级别</option>
            <option value="INFO">INFO</option>
            <option value="WARN">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
          <select
            v-model="store.logsFilter.source"
            class="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
          >
            <option value="ALL">全部来源</option>
            <option v-for="source in sourceOptions" :key="source" :value="source">
              {{ source }}
            </option>
          </select>
          <input
            v-model="store.logsFilter.search"
            type="text"
            placeholder="搜索消息内容"
            class="min-w-[220px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
          />
          <button
            type="button"
            class="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            @click="togglePause"
          >
            {{ store.logsPaused ? '恢复' : '暂停' }}
          </button>
          <button
            type="button"
            class="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            @click="store.clearRealtimeLogs"
          >
            清空
          </button>
        </div>

        <div
          ref="realtimeContainer"
          class="max-h-[62vh] overflow-y-auto rounded-lg border border-slate-200 bg-slate-950 p-3 font-mono text-xs text-slate-200 dark:border-slate-700 dark:bg-slate-900"
        >
          <div v-for="entry in store.filteredLogs" :key="entry.id" class="mb-1 flex flex-wrap items-start gap-x-2 gap-y-1 leading-5">
            <span class="tabular-nums text-slate-400 dark:text-slate-500">{{ formatDate(entry.timestamp) }}</span>
            <span class="rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase" :class="levelClass(entry.level)">
              {{ entry.level }}
            </span>
            <span class="text-cyan-300 dark:text-cyan-400">{{ entry.source }}</span>
            <span class="break-all text-slate-100 dark:text-slate-100">{{ entry.message }}</span>
          </div>
          <p v-if="store.filteredLogs.length === 0" class="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
            暂无日志
          </p>
        </div>

        <div class="flex items-center justify-between text-sm">
          <div class="flex items-center gap-2 text-slate-600 dark:text-slate-300">
            <span class="h-2.5 w-2.5 rounded-full" :class="store.logsConnected ? 'bg-emerald-500' : 'bg-rose-500'" />
            <span>{{ store.logsConnected ? '已连接' : '已断开' }}</span>
          </div>
          <span class="text-slate-500 dark:text-slate-400">显示 {{ store.filteredLogs.length }} / {{ store.logs.length }} 条</span>
        </div>
      </div>

      <div v-else class="space-y-3">
        <div class="flex flex-col gap-2 lg:flex-row lg:items-center">
          <select
            v-model="historyFile"
            class="min-w-[240px] rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
          >
            <option value="">请选择日志文件</option>
            <option v-for="file in store.logFiles" :key="file" :value="file">{{ file }}</option>
          </select>
          <button
            type="button"
            class="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            :disabled="!historyFile"
            @click="loadHistory(0)"
          >
            加载
          </button>
        </div>

        <div class="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              <tr>
                <th class="px-3 py-2 font-medium">时间戳</th>
                <th class="px-3 py-2 font-medium">级别</th>
                <th class="px-3 py-2 font-medium">来源</th>
                <th class="px-3 py-2 font-medium">消息</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in store.logHistory"
                :key="`${entry.id}-${entry.timestamp}`"
                class="border-b border-slate-100 dark:border-slate-700"
              >
                <td class="px-3 py-2 tabular-nums text-slate-600 dark:text-slate-300">{{ formatDate(entry.timestamp) }}</td>
                <td class="px-3 py-2">
                  <span class="rounded px-1.5 py-0.5 text-xs font-medium uppercase" :class="levelClass(entry.level)">{{ entry.level }}</span>
                </td>
                <td class="px-3 py-2 text-slate-700 dark:text-slate-200">{{ entry.source }}</td>
                <td class="px-3 py-2 text-slate-700 dark:text-slate-200">{{ entry.message }}</td>
              </tr>
              <tr v-if="store.logHistory.length === 0">
                <td colspan="4" class="px-3 py-8 text-center text-slate-500 dark:text-slate-400">暂无历史日志</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-end gap-2">
          <button
            type="button"
            class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            :disabled="historyOffset <= 0 || !historyFile"
            @click="loadHistory(historyOffset - pageSize)"
          >
            上一页
          </button>
          <span class="text-sm text-slate-500 dark:text-slate-400">偏移 {{ historyOffset }}</span>
          <button
            type="button"
            class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            :disabled="!canNextHistory || !historyFile"
            @click="loadHistory(historyOffset + pageSize)"
          >
            下一页
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDevtoolsStore } from '@/stores/devtools'

const store = useDevtoolsStore()
const realtimeContainer = ref<HTMLElement | null>(null)
const activeTab = ref<'realtime' | 'history'>('realtime')
const historyFile = ref('')
const historyOffset = ref(0)
const pageSize = 100

const sourceOptions = computed(() => {
  return Array.from(new Set(store.logs.map((entry) => entry.source))).sort((a, b) => a.localeCompare(b))
})

const canNextHistory = computed(() => historyOffset.value + pageSize < store.logHistoryTotal)

function levelClass(level: string): string {
  const normalized = level.toUpperCase()
  if (normalized === 'INFO') {
    return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
  }
  if (normalized === 'WARN' || normalized === 'WARNING') {
    return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
  }
  if (normalized === 'ERROR') {
    return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  }
  return 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

function togglePause() {
  store.logsPaused = !store.logsPaused
}

async function autoScroll() {
  if (store.logsPaused || !realtimeContainer.value) {
    return
  }
  await nextTick()
  realtimeContainer.value.scrollTop = realtimeContainer.value.scrollHeight
}

async function loadHistory(offset: number) {
  if (!historyFile.value) {
    return
  }
  historyOffset.value = Math.max(offset, 0)
  try {
    await store.fetchLogHistory(historyFile.value, historyOffset.value, pageSize)
  } catch {
    // Error is reflected by store.error.
  }
}

watch(
  () => store.filteredLogs.length,
  async () => {
    await autoScroll()
  }
)

onMounted(async () => {
  store.connectLogsWs()
  try {
    await store.fetchLogFiles()
    historyFile.value = store.logFiles[0] ?? ''
    if (historyFile.value) {
      await loadHistory(0)
    }
  } catch {
    // Error is reflected by store.error.
  }
})

onUnmounted(() => {
  store.disconnectLogsWs()
})
</script>
