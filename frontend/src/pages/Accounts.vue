<template>
  <div class="space-y-6">
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
          <button
            type="button"
            class="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700"
            @click="openCreateModal"
          >
            添加账号
          </button>
        </div>
      </div>

      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2 font-medium">ID</th>
              <th class="px-3 py-2 font-medium">邮箱</th>
              <th class="px-3 py-2 font-medium">套餐</th>
              <th class="px-3 py-2 font-medium">状态</th>
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
              <td class="px-3 py-3 tabular-nums">{{ account.id }}</td>
              <td class="px-3 py-3">{{ account.email }}</td>
              <td class="px-3 py-3 uppercase">{{ account.plan }}</td>
              <td class="px-3 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-xs font-medium" :class="statusClass(account.status)">
                  {{ account.status }}
                </span>
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
                    class="rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
                    @click="onDeleteAccount(account.id)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!store.loading && filteredAccounts.length === 0">
              <td colspan="6" class="px-3 py-8 text-center text-sm text-slate-500 dark:text-slate-400">暂无账号</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <Teleport to="body">
      <div
        v-if="showCreateModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="closeCreateModal"
      >
        <div class="w-full max-w-md rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
          <h3 class="text-lg font-semibold text-slate-900 dark:text-slate-200">添加账号</h3>
          <div class="mt-4 space-y-3">
            <div>
              <label class="mb-1 block text-sm text-slate-600 dark:text-slate-400">邮箱</label>
              <input
                v-model="form.email"
                type="email"
                class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm text-slate-600 dark:text-slate-400">密码</label>
              <input
                v-model="form.password"
                type="password"
                class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm text-slate-600 dark:text-slate-400">套餐</label>
              <select
                v-model="form.plan"
                class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200"
              >
                <option value="free">free</option>
                <option value="plus">plus</option>
              </select>
            </div>
          </div>
          <div class="mt-5 flex justify-end gap-2">
            <button
              type="button"
              class="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
              @click="closeCreateModal"
            >
              取消
            </button>
            <button
              type="button"
              class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
              @click="submitCreate"
            >
              确认
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { type AccountStatus, useAccountsStore } from '@/stores/accounts'

const store = useAccountsStore()
const keyword = ref('')
const showCreateModal = ref(false)

const statusOptions: AccountStatus[] = ['active', 'cooling', 'banned', 'expired', 'pending', 'abandoned']

const form = reactive({
  email: '',
  password: '',
  plan: 'free' as 'free' | 'plus'
})

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
      account.status.toLowerCase().includes(q)
    )
  })
})

const statusClassMap: Record<AccountStatus, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  cooling: 'bg-amber-100 text-amber-700',
  banned: 'bg-red-100 text-red-700',
  expired: 'bg-slate-100 text-slate-700',
  pending: 'bg-blue-100 text-blue-700',
  abandoned: 'border border-red-300 text-red-700'
}

function statusClass(status: AccountStatus): string {
  return statusClassMap[status]
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

function openCreateModal() {
  showCreateModal.value = true
}

function closeCreateModal() {
  showCreateModal.value = false
  form.email = ''
  form.password = ''
  form.plan = 'free'
}

async function submitCreate() {
  if (!form.email.trim() || !form.password.trim()) {
    return
  }

  try {
    await store.createAccount({
      email: form.email.trim(),
      password: form.password,
      plan: form.plan
    })
    closeCreateModal()
  } catch {
    // Error is reflected by store.error.
  }
}

async function onStatusChange(id: number, status: AccountStatus) {
  try {
    await store.updateAccountStatus(id, status)
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
  } catch {
    // Error is reflected by store.error.
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
