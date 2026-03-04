<template>
  <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
    <h3 class="text-base font-semibold text-slate-800 dark:text-slate-200">可用模型</h3>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">当前启用的 Codex 模型</p>

    <ul class="mt-4 divide-y divide-slate-100 dark:divide-slate-700">
      <li
        v-for="model in models"
        :key="model.id"
        class="flex items-center justify-between gap-4 py-3"
      >
        <code class="text-sm text-slate-900 dark:text-slate-200">{{ model.id }}</code>
        <span class="text-sm text-slate-500 dark:text-slate-400">{{ model.name }}</span>
      </li>
      <li v-if="models.length === 0" class="py-8 text-center text-sm text-slate-400 dark:text-slate-500">暂无模型</li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { DashboardModel } from '@/stores/dashboard'

defineProps<{
  models: DashboardModel[]
}>()
</script>
