<template>
  <div class="space-y-5">
    <p v-if="store.error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ store.error }}
    </p>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex flex-col gap-2 lg:flex-row lg:items-center">
        <select v-model="filters.level" class="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200">
          <option value="ALL">全部级别</option>
          <option value="INFO">INFO</option>
          <option value="WARN">WARN</option>
          <option value="ERROR">ERROR</option>
        </select>

        <select v-model="filters.source" class="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200">
          <option value="ALL">全部来源</option>
          <option value="system">system</option>
          <option value="api">api</option>
          <option value="pipeline">pipeline</option>
        </select>

        <input
          v-model="filters.search"
          type="text"
          placeholder="搜索日志内容"
          class="min-w-[220px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
        />

        <button
          type="button"
          class="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          @click="applyFilters"
        >
          查询
        </button>
        <button
          type="button"
          class="rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
          @click="onClearLogs"
        >
          清空日志
        </button>
      </div>

      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2 font-medium">时间戳</th>
              <th class="px-3 py-2 font-medium">级别</th>
              <th class="px-3 py-2 font-medium">来源</th>
              <th class="px-3 py-2 font-medium">消息</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in store.logs" :key="log.id" class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700">
              <td class="px-3 py-3 tabular-nums">{{ formatDate(log.timestamp) }}</td>
              <td class="px-3 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-xs font-medium" :class="levelClass(log.level)">
                  {{ log.level }}
                </span>
              </td>
              <td class="px-3 py-3">{{ log.source }}</td>
              <td class="px-3 py-3 text-slate-700 dark:text-slate-200">{{ log.message }}</td>
            </tr>
            <tr v-if="!store.loading && store.logs.length === 0">
              <td colspan="4" class="px-3 py-8 text-center text-sm text-slate-500 dark:text-slate-400">暂无日志记录</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="mt-4 flex items-center justify-end gap-2">
        <button
          type="button"
          class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          :disabled="currentPage <= 1"
          @click="goPrev"
        >
          上一页
        </button>
        <span class="text-sm text-slate-600 dark:text-slate-400">第 {{ currentPage }} 页</span>
        <button
          type="button"
          class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          :disabled="!hasNextPage"
          @click="goNext"
        >
          下一页
        </button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useLogsStore } from '@/stores/logs'

const store = useLogsStore()
const pageSize = 20

const filters = reactive({
  level: 'ALL',
  source: 'ALL',
  search: ''
})

const currentPage = computed(() => store.page)
const hasNextPage = computed(() => store.page * pageSize < store.total)

function levelClass(level: string): string {
  const normalized = level.toUpperCase()
  if (normalized === 'INFO') {
    return 'bg-blue-100 text-blue-700'
  }
  if (normalized === 'WARN' || normalized === 'WARNING') {
    return 'bg-amber-100 text-amber-700'
  }
  if (normalized === 'ERROR') {
    return 'bg-red-100 text-red-700'
  }
  return 'bg-slate-100 text-slate-700'
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

async function fetchPage(page: number) {
  try {
    await store.fetchLogs({
      page,
      limit: pageSize,
      level: filters.level,
      source: filters.source,
      search: filters.search
    })
  } catch {
    // Error is reflected by store.error.
  }
}

async function applyFilters() {
  await fetchPage(1)
}

async function goPrev() {
  if (store.page <= 1) {
    return
  }
  await fetchPage(store.page - 1)
}

async function goNext() {
  if (!hasNextPage.value) {
    return
  }
  await fetchPage(store.page + 1)
}

async function onClearLogs() {
  const confirmed = window.confirm('确认清空所有日志吗？')
  if (!confirmed) {
    return
  }

  try {
    await store.clearLogs()
  } catch {
    // Error is reflected by store.error.
  }
}

onMounted(async () => {
  await fetchPage(1)
})
</script>
