<template>
  <div class="space-y-6">
    <p v-if="notice" class="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
      {{ notice }}
    </p>
    <p v-if="store.error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {{ store.error }}
    </p>

    <section class="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <h2 class="text-base font-semibold text-slate-900 dark:text-slate-100">新增用户</h2>
      <div class="mt-4 grid gap-3 md:grid-cols-5">
        <input v-model.trim="form.username" type="text" placeholder="用户名" class="input" />
        <input v-model="form.password" type="text" placeholder="初始密码 (>=6)" class="input" />
        <input v-model.trim="form.email" type="email" placeholder="邮箱(可选)" class="input" />
        <select v-model="form.permission" class="input">
          <option value="admin">admin</option>
          <option value="operator">operator</option>
          <option value="viewer">viewer</option>
        </select>
        <button type="button" class="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700" @click="onCreateUser">
          创建用户
        </button>
      </div>
    </section>

    <section class="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-slate-900 dark:text-slate-100">用户管理</h2>
        <button type="button" class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50" @click="reload">
          刷新
        </button>
      </div>

      <div class="mt-4 overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-slate-50 text-left text-slate-600 dark:bg-slate-700 dark:text-slate-400">
            <tr>
              <th class="px-3 py-2 font-medium">ID</th>
              <th class="px-3 py-2 font-medium">用户名</th>
              <th class="px-3 py-2 font-medium">邮箱</th>
              <th class="px-3 py-2 font-medium">权限</th>
              <th class="px-3 py-2 font-medium">状态</th>
              <th class="px-3 py-2 font-medium">最后登录</th>
              <th class="px-3 py-2 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="user in store.users"
              :key="user.id"
              class="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700"
            >
              <td class="px-3 py-3 tabular-nums">{{ user.id }}</td>
              <td class="px-3 py-3">{{ user.username }}</td>
              <td class="px-3 py-3">{{ user.email || '-' }}</td>
              <td class="px-3 py-3">
                <select
                  :value="user.permission"
                  class="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-700"
                  @change="onPermissionChange(user.id, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="admin">admin</option>
                  <option value="operator">operator</option>
                  <option value="viewer">viewer</option>
                </select>
              </td>
              <td class="px-3 py-3">
                <label class="inline-flex cursor-pointer items-center gap-2 text-xs">
                  <input type="checkbox" :checked="user.is_active" @change="onActiveChange(user.id, ($event.target as HTMLInputElement).checked)" />
                  {{ user.is_active ? 'active' : 'disabled' }}
                </label>
              </td>
              <td class="px-3 py-3 text-xs text-slate-500">{{ formatDate(user.last_login_at) }}</td>
              <td class="px-3 py-3 text-right">
                <button
                  type="button"
                  class="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700"
                  @click="onResetPassword(user.id)"
                >
                  重置密码
                </button>
              </td>
            </tr>
            <tr v-if="!store.loading && store.users.length === 0">
              <td colspan="7" class="px-3 py-8 text-center text-sm text-slate-500">暂无用户</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { type UserPermission, useUsersStore } from '@/stores/users'

const store = useUsersStore()
const notice = ref('')
const form = reactive({
  username: '',
  password: '',
  email: '',
  permission: 'operator' as UserPermission
})

function pushNotice(message: string) {
  notice.value = message
  window.setTimeout(() => {
    if (notice.value === message) {
      notice.value = ''
    }
  }, 2200)
}

function formatDate(value: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

async function reload() {
  try {
    await store.fetchUsers()
  } catch {
    // Error is reflected by store.error.
  }
}

async function onCreateUser() {
  if (!form.username || !form.password) {
    store.error = '用户名和密码必填'
    return
  }
  try {
    await store.createUser({
      username: form.username,
      password: form.password,
      permission: form.permission,
      email: form.email || null,
      is_active: true
    })
    form.username = ''
    form.password = ''
    form.email = ''
    form.permission = 'operator'
    pushNotice('用户已创建')
  } catch {
    // Error is reflected by store.error.
  }
}

async function onPermissionChange(id: number, value: string) {
  const next = value as UserPermission
  try {
    await store.patchUser(id, { permission: next })
    pushNotice('权限已更新')
  } catch {
    // Error is reflected by store.error.
  }
}

async function onActiveChange(id: number, checked: boolean) {
  try {
    await store.patchUser(id, { is_active: checked })
    pushNotice('状态已更新')
  } catch {
    // Error is reflected by store.error.
  }
}

async function onResetPassword(id: number) {
  const confirmed = window.confirm('确认重置该用户密码？')
  if (!confirmed) return
  try {
    const result = await store.resetPassword(id)
    await navigator.clipboard.writeText(result.new_password)
    pushNotice(`密码已重置并复制（用户: ${result.username}）`)
  } catch (err) {
    if (err instanceof Error && err.message.includes('clipboard')) {
      store.error = '重置成功但复制失败，请检查剪贴板权限'
      return
    }
    // Error is reflected by store.error.
  }
}

onMounted(async () => {
  await reload()
})
</script>

<style scoped>
.input {
  border-radius: 0.5rem;
  border: 1px solid rgb(203 213 225);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}
</style>
