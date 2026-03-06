<template>
  <div v-if="fatalError" class="flex min-h-screen items-center justify-center bg-slate-100 p-6 dark:bg-slate-900">
    <div class="w-full max-w-xl rounded-xl border border-rose-200 bg-white p-6 shadow-sm dark:border-rose-900/40 dark:bg-slate-800">
      <h1 class="text-lg font-semibold text-rose-700 dark:text-rose-300">页面发生错误</h1>
      <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">
        已拦截运行时异常，避免整站白屏。你可以先重试当前页面，或回到仪表盘。
      </p>
      <pre class="mt-4 max-h-48 overflow-auto rounded bg-slate-100 p-3 text-xs text-slate-700 dark:bg-slate-900 dark:text-slate-200">{{ fatalError }}</pre>
      <div class="mt-4 flex gap-2">
        <button
          type="button"
          class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
          @click="clearFatalError"
        >
          重试渲染
        </button>
        <button
          type="button"
          class="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
          @click="goDashboard"
        >
          返回仪表盘
        </button>
      </div>
    </div>
  </div>
  <RouterView v-else />
</template>

<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

const fatalError = ref('')

onErrorCaptured((err) => {
  fatalError.value = err instanceof Error ? err.stack || err.message : String(err)
  return false
})

function clearFatalError() {
  fatalError.value = ''
}

function goDashboard() {
  fatalError.value = ''
  if (typeof window !== 'undefined') {
    window.location.hash = '#/dashboard'
  }
}
</script>
