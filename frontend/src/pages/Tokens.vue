<template>
  <div class="space-y-5">
    <p v-if="store.error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ store.error }}
    </p>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="text-xl font-semibold text-slate-900 dark:text-slate-200">令牌管理</h2>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">管理 API 访问令牌</p>
        </div>
        <button
          type="button"
          class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
          @click="showCreateModal = true"
        >
          创建令牌
        </button>
      </div>

      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2 font-medium">名称</th>
              <th class="px-3 py-2 font-medium">Key</th>
              <th class="px-3 py-2 font-medium">创建时间</th>
              <th class="px-3 py-2 font-medium">最后使用</th>
              <th class="px-3 py-2 font-medium">请求数</th>
              <th class="px-3 py-2 font-medium">Token 数</th>
              <th class="px-3 py-2 font-medium">状态</th>
              <th class="px-3 py-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="token in store.tokens"
              :key="token.id"
              class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700"
            >
              <td class="px-3 py-3">{{ token.name }}</td>
              <td class="px-3 py-3 font-mono">{{ maskKey(token.key) }}</td>
              <td class="px-3 py-3 tabular-nums">{{ formatDate(token.created_at) }}</td>
              <td class="px-3 py-3 tabular-nums">{{ token.last_used_at ? formatDate(token.last_used_at) : '-' }}</td>
              <td class="px-3 py-3 tabular-nums">{{ formatNumber(token.total_requests) }}</td>
              <td class="px-3 py-3 tabular-nums">{{ formatNumber(token.total_tokens) }}</td>
              <td class="px-3 py-3">
                <span
                  class="rounded-full px-2.5 py-0.5 text-xs font-medium"
                  :class="token.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'"
                >
                  {{ token.is_active ? '活跃' : '已撤销' }}
                </span>
              </td>
              <td class="px-3 py-3">
                <button
                  v-if="token.is_active"
                  type="button"
                  class="rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
                  @click="onRevoke(token.id)"
                >
                  撤销
                </button>
              </td>
            </tr>
            <tr v-if="!store.loading && store.tokens.length === 0">
              <td colspan="8" class="px-3 py-8 text-center text-sm text-slate-500 dark:text-slate-400">暂无令牌</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="showCreateModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="closeModal"
      >
        <div class="w-full max-w-md rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-200">创建令牌</h3>

          <template v-if="!createdKey">
            <div class="mt-4">
              <label class="mb-1 block text-sm text-slate-600 dark:text-slate-400">令牌名称</label>
              <input
                v-model="tokenName"
                type="text"
                class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
              />
            </div>
            <div class="mt-5 flex justify-end gap-2">
              <button
                type="button"
                class="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                @click="closeModal"
              >
                取消
              </button>
              <button
                type="button"
                class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                @click="onCreate"
              >
                创建
              </button>
            </div>
          </template>

          <template v-else>
            <p class="mt-3 text-sm text-amber-700">请立即复制，关闭后不再显示</p>
            <div class="mt-3 rounded-lg bg-slate-100 p-3 font-mono text-sm text-slate-900 dark:bg-slate-700 dark:text-slate-200">
              {{ createdKey }}
            </div>
            <div class="mt-4 flex justify-end gap-2">
              <button
                type="button"
                class="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                @click="copyKey"
              >
                一键复制
              </button>
              <button
                type="button"
                class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
                @click="closeModal"
              >
                关闭
              </button>
            </div>
          </template>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useTokensStore } from '@/stores/tokens'

const store = useTokensStore()
const showCreateModal = ref(false)
const tokenName = ref('')
const createdKey = ref('')

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function maskKey(key?: string): string {
  if (!key) {
    return '********'
  }
  return `${key.slice(0, 8)}****`
}

function closeModal() {
  showCreateModal.value = false
  tokenName.value = ''
  createdKey.value = ''
}

async function onCreate() {
  if (!tokenName.value.trim()) {
    return
  }

  try {
    const token = await store.createToken(tokenName.value.trim())
    createdKey.value = token.key ?? ''
    tokenName.value = ''
  } catch {
    // Error is reflected by store.error.
  }
}

async function copyKey() {
  if (!createdKey.value) {
    return
  }

  try {
    await navigator.clipboard.writeText(createdKey.value)
  } catch {
    // Clipboard write failure is non-blocking for this flow.
  }
}

async function onRevoke(id: number) {
  const confirmed = window.confirm('确认撤销该令牌吗？')
  if (!confirmed) {
    return
  }

  try {
    await store.revokeToken(id)
  } catch {
    // Error is reflected by store.error.
  }
}

onMounted(async () => {
  try {
    await store.fetchTokens()
  } catch {
    // Error is reflected by store.error.
  }
})
</script>
