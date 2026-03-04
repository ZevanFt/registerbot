<template>
  <div
    class="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 via-white to-cyan-50 px-4 py-10 dark:from-slate-950 dark:via-slate-900 dark:to-slate-800"
  >
    <div class="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl dark:border-slate-700 dark:bg-slate-800">
      <h1 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">管理端登录</h1>
      <p class="mt-2 text-sm text-slate-500 dark:text-slate-400">登录后可访问 codex2api 管理后台。</p>

      <p
        v-if="errorMessage"
        class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-600 dark:border-rose-900/60 dark:bg-rose-900/20 dark:text-rose-300"
      >
        {{ errorMessage }}
      </p>

      <form class="mt-6 space-y-4" @submit.prevent="onSubmit">
        <label class="block text-sm font-medium text-slate-700 dark:text-slate-300">
          用户名
          <input
            v-model.trim="form.username"
            type="text"
            autocomplete="username"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-200 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-cyan-400 dark:focus:ring-cyan-900/60"
            placeholder="请输入用户名"
          />
        </label>

        <label class="block text-sm font-medium text-slate-700 dark:text-slate-300">
          密码
          <input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-200 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-cyan-400 dark:focus:ring-cyan-900/60"
            placeholder="请输入密码"
          />
        </label>

        <button
          type="submit"
          class="w-full rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="store.loading"
        >
          {{ store.loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const store = useAuthStore()
const errorMessage = ref('')
const form = reactive({
  username: '',
  password: ''
})

const onSubmit = async () => {
  errorMessage.value = ''
  if (!form.username || !form.password) {
    errorMessage.value = '请输入用户名和密码'
    return
  }

  try {
    await store.login(form.username, form.password)
    await router.replace('/dashboard')
  } catch {
    errorMessage.value = '用户名或密码错误'
  }
}
</script>
