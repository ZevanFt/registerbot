<template>
  <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
    <h3 class="text-base font-semibold text-slate-800 dark:text-slate-200">服务状态</h3>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">运行时信息</p>

    <dl class="mt-4 space-y-3 text-sm">
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">运行时间</dt>
        <dd class="font-medium tabular-nums text-slate-800 dark:text-slate-200">{{ uptimeMinutes }} 分钟</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">调度模式</dt>
        <dd class="font-medium text-slate-800 dark:text-slate-200">{{ scheduleMode }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">版本</dt>
        <dd class="font-medium text-slate-800 dark:text-slate-200">{{ version }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">Python</dt>
        <dd class="font-medium text-slate-800 dark:text-slate-200">{{ pythonVersion }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">上游状态</dt>
        <dd class="font-medium" :class="upstreamStatusClass">{{ upstreamStatus }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">上游地址</dt>
        <dd class="max-w-[14rem] truncate font-medium text-slate-800 dark:text-slate-200" :title="openaiBaseUrl">
          {{ openaiBaseUrl }}
        </dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">chat2api 模式</dt>
        <dd class="font-medium text-slate-800 dark:text-slate-200">{{ chat2apiMode ? '是' : '否' }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  uptimeSeconds: number
  pythonVersion: string
  scheduleMode?: string
  version?: string
  upstreamStatus?: string
  openaiBaseUrl?: string
  chat2apiMode?: boolean
}>()

const uptimeMinutes = computed(() => Math.floor(props.uptimeSeconds / 60))
const scheduleMode = computed(() => props.scheduleMode || 'round-robin')
const version = computed(() => props.version || '-')
const upstreamStatus = computed(() => props.upstreamStatus || 'unknown')
const openaiBaseUrl = computed(() => props.openaiBaseUrl || '-')
const chat2apiMode = computed(() => Boolean(props.chat2apiMode))
const upstreamStatusClass = computed(() => {
  const value = upstreamStatus.value.toLowerCase()
  if (value === 'reachable') {
    return 'text-emerald-600 dark:text-emerald-400'
  }
  if (value === 'unreachable') {
    return 'text-rose-600 dark:text-rose-400'
  }
  return 'text-slate-700 dark:text-slate-200'
})
</script>
