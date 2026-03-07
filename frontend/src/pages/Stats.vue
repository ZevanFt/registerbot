<template>
  <div class="space-y-5">
    <p v-if="store.error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ store.error }}
    </p>
    <p class="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">
      统计页数据为真实聚合数据，来源于后端 <code>stats.db/usage_logs</code>；模型分布来自实际请求日志，不是前端 Mock。
    </p>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-200">今日汇总</h2>
      <div class="mt-4 grid gap-4 md:grid-cols-3">
        <StatCard label="总请求数" :value="store.summary.total_requests" />
        <StatCard label="总 Token 数" :value="formatNumber(store.summary.total_tokens)" />
        <StatCard label="平均延迟" :value="formattedAvgLatency" />
      </div>
    </section>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-200">24 小时请求分布</h2>
        <div class="flex gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span>24h总请求: {{ formatNumber(hourlyMeta.totalRequests) }}</span>
          <span>峰值: {{ hourlyMeta.peakLabel }} ({{ formatNumber(hourlyMeta.peakRequests) }})</span>
          <span>平均: {{ hourlyMeta.avgRequests.toFixed(1) }}/h</span>
        </div>
      </div>
      <div class="mt-4 overflow-x-auto">
        <div class="relative min-w-[780px] rounded-lg border border-slate-100 px-3 pb-6 pt-2 dark:border-slate-700">
          <div
            v-for="tick in yTicks"
            :key="tick.label"
            class="pointer-events-none absolute left-3 right-3 border-t border-dashed border-slate-200 dark:border-slate-700"
            :style="{ bottom: `${tick.offset}px` }"
          />
          <div class="mb-1 flex justify-between text-[10px] text-slate-400 dark:text-slate-500">
            <span v-for="tick in yTicks" :key="`label-${tick.label}`">{{ tick.label }}</span>
          </div>
          <div class="flex items-end gap-2">
            <div v-for="item in hourlyBars" :key="item.hour" class="flex w-7 flex-col items-center gap-1">
            <div
              class="w-full rounded-t transition-all"
              :class="item.isPeak ? 'bg-amber-500' : 'bg-blue-500'"
              :style="{ height: `${item.height}px` }"
              :title="`${item.label}: 请求 ${item.requests} / Token ${item.tokens}`"
            />
            <span class="text-[10px] text-slate-500 dark:text-slate-400">{{ item.tickLabel }}</span>
          </div>
          </div>
        </div>
        <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">
          金色为峰值小时，蓝色为其余小时；0 请求小时显示为极细基线，避免视觉误导。
        </p>
          </div>
    </section>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-200">模型使用分布</h2>
      <div class="mt-4 space-y-3">
        <div v-for="item in modelRows" :key="item.model" class="space-y-1">
          <div class="flex items-center justify-between text-sm">
            <span class="text-slate-700 dark:text-slate-200">{{ item.model }}</span>
            <span class="text-slate-500 dark:text-slate-400">{{ item.percent.toFixed(1) }}%</span>
          </div>
          <div class="h-2 w-full rounded bg-slate-100 dark:bg-slate-700">
            <div class="h-2 rounded" :class="item.color" :style="{ width: `${item.percent}%` }" />
          </div>
        </div>
        <p v-if="modelRows.length === 0" class="text-sm text-slate-500 dark:text-slate-400">暂无模型统计</p>
      </div>
    </section>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-200">账号用量排行</h2>
      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2 font-medium">邮箱</th>
              <th class="px-3 py-2 font-medium">请求数</th>
              <th class="px-3 py-2 font-medium">Token 数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rankedAccounts" :key="row.email" class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700">
              <td class="px-3 py-3">{{ row.email }}</td>
              <td class="px-3 py-3 tabular-nums">{{ formatNumber(row.requests) }}</td>
              <td class="px-3 py-3 tabular-nums">{{ formatNumber(row.total_tokens) }}</td>
            </tr>
            <tr v-if="rankedAccounts.length === 0">
              <td colspan="3" class="px-3 py-8 text-center text-sm text-slate-500 dark:text-slate-400">暂无账号用量数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import StatCard from '@/components/StatCard.vue'
import { useStatsStore } from '@/stores/stats'

const store = useStatsStore()
const barMaxHeight = 140
const barMinHeight = 2
const modelColors = ['bg-blue-500', 'bg-emerald-500', 'bg-amber-500', 'bg-cyan-500', 'bg-indigo-500', 'bg-rose-500']

const hourlyBars = computed(() => {
  const map = new Map<number, { requests: number; tokens: number }>()
  for (const item of store.hourlyData) {
    map.set(item.hour, { requests: item.requests, tokens: item.tokens })
  }

  const base = Array.from({ length: 24 }, (_, hour) => ({
    hour,
    requests: map.get(hour)?.requests ?? 0,
    tokens: map.get(hour)?.tokens ?? 0
  }))

  const maxRequests = Math.max(...base.map((item) => item.requests), 1)
  const peak = Math.max(...base.map((item) => item.requests))

  return base.map((item) => ({
    ...item,
    label: String(item.hour).padStart(2, '0'),
    tickLabel: item.hour % 2 === 0 ? `${String(item.hour).padStart(2, '0')}` : '',
    isPeak: peak > 0 && item.requests === peak,
    height:
      item.requests <= 0
        ? barMinHeight
        : Math.max(10, Math.round((item.requests / maxRequests) * barMaxHeight))
  }))
})

const hourlyMeta = computed(() => {
  const totalRequests = hourlyBars.value.reduce((sum, item) => sum + item.requests, 0)
  const peakItem = hourlyBars.value.reduce(
    (acc, item) => (item.requests > acc.requests ? item : acc),
    { hour: 0, requests: 0, label: '00' } as { hour: number; requests: number; label: string }
  )
  return {
    totalRequests,
    peakRequests: peakItem.requests,
    peakLabel: `${peakItem.label}:00`,
    avgRequests: totalRequests / 24
  }
})

const yTicks = computed(() => {
  const maxRequests = Math.max(...hourlyBars.value.map((item) => item.requests), 1)
  return [0, 0.33, 0.66, 1].map((ratio) => ({
    label: String(Math.round(maxRequests * ratio)),
    offset: Math.round(barMaxHeight * ratio) + 24
  }))
})

const modelRows = computed(() => {
  const total = store.modelDist.reduce((sum, item) => sum + item.requests, 0)
  if (total === 0) {
    return []
  }

  return store.modelDist.map((item, index) => ({
    ...item,
    percent: (item.requests / total) * 100,
    color: modelColors[index % modelColors.length]
  }))
})

const rankedAccounts = computed(() => {
  return [...store.accountUsage].sort((a, b) => b.requests - a.requests)
})

const formattedAvgLatency = computed(() => `${Number(store.summary.avg_latency ?? 0).toFixed(2)} ms`)

function formatNumber(value: number): string {
  const parsed = Number(value)
  return new Intl.NumberFormat('zh-CN').format(Number.isFinite(parsed) ? parsed : 0)
}

onMounted(async () => {
  try {
    await Promise.all([
      store.fetchSummary(),
      store.fetchHourly(),
      store.fetchDaily(),
      store.fetchModels(),
      store.fetchAccountUsage()
    ])
  } catch {
    // Error is reflected by store.error.
  }
})
</script>
