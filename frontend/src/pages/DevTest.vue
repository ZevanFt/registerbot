<template>
  <div class="space-y-4">
    <p
      v-if="store.error"
      class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-900/20 dark:text-rose-300"
    >
      {{ store.error }}
    </p>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-100">测试面板</h2>
          <p class="text-sm text-slate-500 dark:text-slate-400">执行全量测试或指定测试文件</p>
        </div>
        <div class="text-right text-sm">
          <p class="font-medium" :class="store.testRunning ? 'text-blue-600 dark:text-blue-400' : 'text-slate-700 dark:text-slate-300'">
            状态: {{ store.testRunning ? 'running' : 'idle' }}
          </p>
          <p class="text-slate-500 dark:text-slate-400">最近运行: {{ latestRunTime }}</p>
        </div>
      </div>

      <div class="mt-4 flex flex-col gap-2 lg:flex-row lg:items-center">
        <button
          type="button"
          class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          :disabled="store.testRunning"
          @click="runAll"
        >
          运行全部测试
        </button>
        <input
          v-model="testFile"
          type="text"
          placeholder="tests/example.spec.ts"
          class="min-w-[260px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
        />
        <button
          type="button"
          class="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
          :disabled="store.testRunning || !testFile.trim()"
          @click="runSingle"
        >
          运行指定文件
        </button>
      </div>

      <div
        v-if="lastExitCode !== null"
        class="mt-4 rounded-lg px-3 py-2 text-sm font-medium"
        :class="
          lastExitCode === 0
            ? 'border border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-900/20 dark:text-emerald-300'
            : 'border border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-900/20 dark:text-rose-300'
        "
      >
        {{ lastExitCode === 0 ? '测试通过 (exit_code=0)' : `测试失败 (exit_code=${lastExitCode})` }}
      </div>

      <div
        ref="outputContainer"
        class="mt-4 h-[52vh] overflow-y-auto rounded-lg border border-slate-200 bg-black/95 p-3 font-mono text-xs leading-5 dark:border-slate-700"
      >
        <p v-for="(line, index) in store.testOutput" :key="`${line.timestamp}-${index}`" :class="lineClass(line)">
          {{ renderLine(line) }}
        </p>
        <p v-if="store.testOutput.length === 0" class="text-slate-500 dark:text-slate-500">暂无测试输出</p>
      </div>

      <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
        汇总: {{ summaryText }}
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDevtoolsStore, type TestLine } from '@/stores/devtools'

const store = useDevtoolsStore()
const outputContainer = ref<HTMLElement | null>(null)
const testFile = ref('')

const lastExitLine = computed(() => {
  const output = store.testOutput
  for (let index = output.length - 1; index >= 0; index -= 1) {
    if (output[index].type === 'exit') {
      return output[index]
    }
  }
  return null
})

const lastExitCode = computed(() => lastExitLine.value?.exit_code ?? null)

const latestRunTime = computed(() => {
  if (!lastExitLine.value?.timestamp) {
    return '-'
  }
  return new Date(lastExitLine.value.timestamp).toLocaleString('zh-CN', { hour12: false })
})

const summary = computed(() => {
  const lineSummary = lastExitLine.value?.summary
  if (lineSummary) {
    return {
      passed: lineSummary.passed ?? 0,
      failed: lineSummary.failed ?? 0,
      warnings: lineSummary.warnings ?? 0
    }
  }
  return {
    passed: countMatch(/passed/i),
    failed: countMatch(/failed/i),
    warnings: countMatch(/warn(ing)?/i)
  }
})

const summaryText = computed(() => `${summary.value.passed} passed, ${summary.value.failed} failed, ${summary.value.warnings} warnings`)

function countMatch(pattern: RegExp): number {
  return store.testOutput.reduce((count, line) => (pattern.test(line.line) ? count + 1 : count), 0)
}

function lineClass(line: TestLine): string {
  if (line.type === 'stderr' || /failed|error/i.test(line.line)) {
    return 'text-rose-400'
  }
  if (/passed|success/i.test(line.line)) {
    return 'text-emerald-400'
  }
  if (line.type === 'exit') {
    return 'text-cyan-400'
  }
  return 'text-slate-100'
}

function renderLine(line: TestLine): string {
  if (line.type === 'exit') {
    const code = line.exit_code ?? '-'
    return `[exit] code=${code} ${line.line || ''}`.trim()
  }
  return line.line
}

async function runAll() {
  try {
    await store.runTest()
  } catch {
    // Error is reflected by store.error.
  }
}

async function runSingle() {
  if (!testFile.value.trim()) {
    return
  }
  try {
    await store.runTest(testFile.value)
  } catch {
    // Error is reflected by store.error.
  }
}

async function autoScroll() {
  if (!outputContainer.value) {
    return
  }
  await nextTick()
  outputContainer.value.scrollTop = outputContainer.value.scrollHeight
}

watch(
  () => store.testOutput.length,
  async () => {
    await autoScroll()
  }
)

onMounted(async () => {
  store.connectTestWs()
  try {
    await store.fetchLastTestOutput()
  } catch {
    // Error is reflected by store.error.
  }
})

onUnmounted(() => {
  store.disconnectTestWs()
})
</script>
