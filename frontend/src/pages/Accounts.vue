<template>
  <div class="space-y-6">
    <p v-if="notice" class="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
      {{ notice }}
    </p>
    <p v-if="store.error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ store.error }}
    </p>

    <section class="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 class="text-xl font-semibold text-slate-900 dark:text-slate-200">账号管理</h2>
        <div class="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <input
            v-model="keyword"
            type="text"
            placeholder="搜索邮箱/ID"
            class="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
          />
          <select
            v-model="importConflictStrategy"
            class="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
          >
            <option value="skip">导入冲突: 跳过</option>
            <option value="overwrite">导入冲突: 覆盖</option>
          </select>
          <button type="button" class="rounded-lg bg-slate-600 px-4 py-2 text-sm text-white hover:bg-slate-700" @click="triggerImport">
            导入账号
          </button>
          <button
            type="button"
            class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-60"
            :disabled="selectedIds.length === 0"
            @click="exportSelected"
          >
            导出所选 ({{ selectedIds.length }})
          </button>
          <button
            type="button"
            class="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-60"
            :disabled="filteredAccounts.length === 0"
            @click="exportFiltered"
          >
            导出筛选 ({{ filteredAccounts.length }})
          </button>
          <input ref="importFileInput" type="file" accept="application/json" class="hidden" @change="onImportFile" />
        </div>
      </div>

      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2 font-medium">
                <input type="checkbox" :checked="allSelected" @change="toggleSelectAll(($event.target as HTMLInputElement).checked)" />
              </th>
              <th class="px-3 py-2 font-medium">ID</th>
              <th class="px-3 py-2 font-medium">邮箱</th>
              <th class="px-3 py-2 font-medium">套餐</th>
              <th class="px-3 py-2 font-medium">状态</th>
              <th class="px-3 py-2 font-medium">运行状态</th>
              <th class="px-3 py-2 font-medium">Token状态</th>
              <th class="px-3 py-2 font-medium">失败次数</th>
              <th class="px-3 py-2 font-medium">最后错误</th>
              <th class="px-3 py-2 font-medium">创建时间</th>
              <th class="px-3 py-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="account in filteredAccounts"
              :key="account.id"
              class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700"
            >
              <td class="px-3 py-3">
                <input type="checkbox" :checked="selectedIds.includes(account.id)" @change="toggleSelect(account.id, ($event.target as HTMLInputElement).checked)" />
              </td>
              <td class="px-3 py-3 tabular-nums">{{ account.id }}</td>
              <td class="px-3 py-3">{{ account.email }}</td>
              <td class="px-3 py-3 uppercase">{{ account.plan }}</td>
              <td class="px-3 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-xs font-medium" :class="statusClass(account.status)">
                  {{ account.status }}
                </span>
              </td>
              <td class="px-3 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-xs font-medium" :class="runtimeStatusClass(account.runtime_status)">
                  {{ account.runtime_status || 'unknown' }}
                </span>
              </td>
              <td class="px-3 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-xs font-medium" :class="tokenStatusClass(account.token_status)">
                  {{ account.token_status || 'unknown' }}
                </span>
              </td>
              <td class="px-3 py-3 tabular-nums">{{ account.consecutive_failures ?? 0 }}</td>
              <td class="max-w-[20rem] px-3 py-3 text-xs text-slate-500 dark:text-slate-400">
                {{ formatFailureReason(account.last_failure_reason) }}
              </td>
              <td class="px-3 py-3 tabular-nums">{{ formatDate(account.created_at) }}</td>
              <td class="px-3 py-3">
                <div class="flex items-center gap-2">
                  <select
                    :value="account.status"
                    class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
                    @change="onStatusChange(account.id, ($event.target as HTMLSelectElement).value as AccountStatus)"
                  >
                    <option v-for="status in statusOptions" :key="status" :value="status">{{ status }}</option>
                  </select>
                  <button
                    type="button"
                    class="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
                    @click="onRevealPassword(account.id)"
                  >
                    查看密码
                  </button>
                  <button
                    type="button"
                    class="rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
                    @click="onDeleteAccount(account.id)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!store.loading && filteredAccounts.length === 0">
              <td colspan="11" class="px-3 py-8 text-center text-sm text-slate-500 dark:text-slate-400">暂无账号</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="showPasswordModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="closePasswordModal"
      >
        <div class="w-full max-w-xl rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-200">管理员明文密码查看</h3>
          <p class="mt-2 text-sm text-amber-700">敏感信息，仅用于管理员排障与验证。</p>
          <div class="mt-3 rounded-lg bg-slate-100 p-3 text-sm dark:bg-slate-700">
            <p class="font-medium text-slate-700 dark:text-slate-200">{{ revealedEmail }}</p>
            <p class="mt-1 break-all font-mono text-slate-900 dark:text-slate-100">{{ revealedPassword }}</p>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button
              type="button"
              class="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
              @click="copyRevealedPassword"
            >
              复制密码
            </button>
            <button
              type="button"
              class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
              @click="closePasswordModal"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { type AccountStatus, useAccountsStore } from '@/stores/accounts'

const store = useAccountsStore()
const keyword = ref('')
const selectedIds = ref<number[]>([])
const importFileInput = ref<HTMLInputElement | null>(null)
const importConflictStrategy = ref<'skip' | 'overwrite'>('skip')
const notice = ref('')

const showPasswordModal = ref(false)
const revealedEmail = ref('')
const revealedPassword = ref('')

const statusOptions: AccountStatus[] = ['active', 'cooling', 'banned', 'expired', 'pending', 'abandoned']

const filteredAccounts = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) {
    return store.accounts
  }

  return store.accounts.filter((account) => {
    return (
      account.email.toLowerCase().includes(q) ||
      String(account.id).includes(q) ||
      account.plan.toLowerCase().includes(q) ||
      account.status.toLowerCase().includes(q) ||
      String(account.runtime_status || '').toLowerCase().includes(q) ||
      String(account.token_status || '').toLowerCase().includes(q) ||
      String(account.last_failure_reason || '').toLowerCase().includes(q)
    )
  })
})

const allSelected = computed(() => {
  if (filteredAccounts.value.length === 0) return false
  return filteredAccounts.value.every((item) => selectedIds.value.includes(item.id))
})

const statusClassMap: Record<AccountStatus, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  cooling: 'bg-amber-100 text-amber-700',
  banned: 'bg-red-100 text-red-700',
  expired: 'bg-slate-100 text-slate-700',
  pending: 'bg-blue-100 text-blue-700',
  abandoned: 'border border-red-300 text-red-700'
}

function pushNotice(message: string) {
  notice.value = message
  window.setTimeout(() => {
    if (notice.value === message) {
      notice.value = ''
    }
  }, 2200)
}

function statusClass(status: AccountStatus): string {
  return statusClassMap[status]
}

function runtimeStatusClass(value: string | null): string {
  const status = (value || 'unknown').toLowerCase()
  if (status === 'active') return 'bg-emerald-100 text-emerald-700'
  if (status === 'cooling' || status === 'usage_limited') return 'bg-amber-100 text-amber-700'
  if (status === 'banned') return 'bg-red-100 text-red-700'
  return 'bg-slate-100 text-slate-700'
}

function tokenStatusClass(value: string | null): string {
  const status = (value || 'unknown').toLowerCase()
  if (status === 'valid' || status === 'expiring') return 'bg-emerald-100 text-emerald-700'
  if (status === 'refreshing') return 'bg-amber-100 text-amber-700'
  if (status === 'expired' || status === 'invalid_grant' || status === 'refresh_failed') {
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

function formatFailureReason(value: string | null): string {
  if (!value) return '-'
  if (value.length <= 80) return value
  return `${value.slice(0, 80)}...`
}

function toggleSelect(id: number, checked: boolean) {
  if (checked) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value = [...selectedIds.value, id]
    }
    return
  }
  selectedIds.value = selectedIds.value.filter((item) => item !== id)
}

function toggleSelectAll(checked: boolean) {
  if (!checked) {
    const ids = new Set(filteredAccounts.value.map((item) => item.id))
    selectedIds.value = selectedIds.value.filter((id) => !ids.has(id))
    return
  }

  const merged = new Set(selectedIds.value)
  for (const item of filteredAccounts.value) {
    merged.add(item.id)
  }
  selectedIds.value = Array.from(merged)
}

async function onStatusChange(id: number, status: AccountStatus) {
  try {
    await store.updateAccountStatus(id, status)
    pushNotice('账号状态已更新')
  } catch {
    // Error is reflected by store.error.
  }
}

async function onDeleteAccount(id: number) {
  const confirmed = window.confirm('确认删除该账号吗？')
  if (!confirmed) {
    return
  }

  try {
    await store.deleteAccount(id)
    selectedIds.value = selectedIds.value.filter((item) => item !== id)
    pushNotice('账号已删除')
  } catch {
    // Error is reflected by store.error.
  }
}

function triggerImport() {
  importFileInput.value?.click()
}

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  if (!file) return

  try {
    const text = await file.text()
    const parsed = JSON.parse(text) as { accounts?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>
    const accounts = Array.isArray(parsed) ? parsed : (parsed.accounts ?? [])
    if (!Array.isArray(accounts) || accounts.length === 0) {
      throw new Error('文件中没有可导入账号')
    }

    const result = await store.importAccounts({
      conflict_strategy: importConflictStrategy.value,
      accounts,
    })
    pushNotice(`导入完成：新增 ${result.imported}，覆盖 ${result.updated}，跳过 ${result.skipped}，失败 ${result.failed}`)
  } catch (err) {
    store.error = err instanceof Error ? err.message : '导入失败'
  } finally {
    if (input) input.value = ''
  }
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

async function exportSelected() {
  if (selectedIds.value.length === 0) return
  try {
    const payload = await store.exportAccounts(selectedIds.value)
    downloadJson(`accounts-selected-${new Date().toISOString().slice(0, 10)}.json`, payload)
    pushNotice(`已导出 ${payload.count} 个账号`)
  } catch {
    // Error is reflected by store.error.
  }
}

async function exportFiltered() {
  const ids = filteredAccounts.value.map((item) => item.id)
  if (ids.length === 0) return
  try {
    const payload = await store.exportAccounts(ids)
    downloadJson(`accounts-filtered-${new Date().toISOString().slice(0, 10)}.json`, payload)
    pushNotice(`已导出 ${payload.count} 个账号`)
  } catch {
    // Error is reflected by store.error.
  }
}

async function onRevealPassword(id: number) {
  const confirmed = window.confirm('确认查看该账号明文密码？仅限管理员排障。')
  if (!confirmed) return
  try {
    const result = await store.revealAccountPassword(id)
    revealedEmail.value = result.email
    revealedPassword.value = result.password
    showPasswordModal.value = true
  } catch {
    // Error is reflected by store.error.
  }
}

function closePasswordModal() {
  showPasswordModal.value = false
  revealedEmail.value = ''
  revealedPassword.value = ''
}

async function copyRevealedPassword() {
  if (!revealedPassword.value) return
  try {
    await navigator.clipboard.writeText(revealedPassword.value)
    pushNotice('密码已复制')
  } catch {
    store.error = '复制失败：请检查浏览器剪贴板权限'
  }
}

onMounted(async () => {
  try {
    await store.fetchAccounts()
  } catch {
    // Error is reflected by store.error.
  }
})
</script>
