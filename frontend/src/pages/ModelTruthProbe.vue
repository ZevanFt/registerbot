<template>
  <div class="space-y-4">
    <p v-if="error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{{ error }}</p>

    <section class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-100">模型真值探测</h2>
          <p class="text-sm text-slate-500 dark:text-slate-400">独立探测声明模型与实际返回模型映射</p>
        </div>
        <button
          type="button"
          class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-60"
          :disabled="loading"
          @click="runProbe"
        >
          {{ loading ? '探测中...' : '开始探测' }}
        </button>
      </div>

      <div class="mt-4 grid gap-3 md:grid-cols-2">
        <label class="block text-sm">
          <span class="mb-1 block text-slate-600 dark:text-slate-300">候选模型（逗号分隔）</span>
          <input
            v-model="modelsInput"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
            placeholder="gpt-4o-mini, gpt-4o, o3-mini"
          />
        </label>
        <label class="block text-sm">
          <span class="mb-1 block text-slate-600 dark:text-slate-300">最大探测数</span>
          <input
            v-model.number="maxModels"
            type="number"
            min="1"
            max="20"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700"
          />
        </label>
      </div>

      <div v-if="summary" class="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:bg-slate-700 dark:text-slate-200">
        总数 {{ summary.total }}，成功 {{ summary.success }}，失败 {{ summary.failed }}
      </div>

      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-300">
            <tr>
              <th class="px-3 py-2 font-medium">声明模型</th>
              <th class="px-3 py-2 font-medium">实际模型</th>
              <th class="px-3 py-2 font-medium">状态码</th>
              <th class="px-3 py-2 font-medium">结果</th>
              <th class="px-3 py-2 font-medium">错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="`${row.declared_model}-${row.started_at}`" class="border-b border-slate-100 dark:border-slate-700">
              <td class="px-3 py-3 font-mono">{{ row.declared_model }}</td>
              <td class="px-3 py-3 font-mono">{{ row.actual_model || '-' }}</td>
              <td class="px-3 py-3">{{ row.status_code }}</td>
              <td class="px-3 py-3" :class="row.probe_success ? 'text-emerald-600' : 'text-rose-600'">
                {{ row.probe_success ? 'success' : 'failed' }}
              </td>
              <td class="px-3 py-3 text-xs text-slate-500">{{ row.error || '-' }}</td>
            </tr>
            <tr v-if="rows.length === 0">
              <td colspan="5" class="px-3 py-8 text-center text-slate-500">暂无探测结果</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { apiPost } from '@/api/client'

interface ProbeRow {
  declared_model: string
  status_code: number
  probe_success: boolean
  actual_model: string
  error: string
  started_at: string
}

const loading = ref(false)
const error = ref('')
const modelsInput = ref('')
const maxModels = ref(8)
const rows = ref<ProbeRow[]>([])
const summary = ref<{ total: number; success: number; failed: number } | null>(null)

async function runProbe() {
  loading.value = true
  error.value = ''
  try {
    const models = modelsInput.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    const payload = await apiPost<{ total: number; success: number; failed: number; results: ProbeRow[] }>(
      '/devtools/models/truth-probe',
      {
        models,
        max_models: maxModels.value,
      }
    )
    rows.value = payload.results
    summary.value = {
      total: payload.total,
      success: payload.success,
      failed: payload.failed,
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型真值探测失败'
  } finally {
    loading.value = false
  }
}
</script>
