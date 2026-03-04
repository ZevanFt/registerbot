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
        <dd class="font-medium text-slate-800 dark:text-slate-200">轮询</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">版本</dt>
        <dd class="font-medium text-slate-800 dark:text-slate-200">1.0.0</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500 dark:text-slate-400">Python</dt>
        <dd class="font-medium text-slate-800 dark:text-slate-200">{{ pythonVersion }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  uptimeSeconds: number
  pythonVersion: string
}>()

const uptimeMinutes = computed(() => Math.floor(props.uptimeSeconds / 60))
</script>
