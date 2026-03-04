<template>
  <div class="space-y-5">
    <p v-if="store.error" class="msg msg-error">{{ store.error }}</p>
    <p v-if="saved" class="msg msg-ok">保存成功</p>

    <!-- 管理员设置 -->
    <section class="card">
      <h2 class="card-title">管理员设置</h2>
      <div class="grid gap-3 md:grid-cols-2">
        <div><label class="lbl">用户名</label><input v-model="form.admin.username" class="ipt" /></div>
        <div>
          <label class="lbl">密码</label><input v-model="form.admin.password" type="password" class="ipt" />
          <p class="hint">*** 表示未修改</p>
        </div>
        <div>
          <label class="lbl">JWT 密钥</label><input v-model="form.admin.jwt_secret" type="password" class="ipt" />
          <p class="hint">生产环境需 32+ 字节随机串</p>
        </div>
        <div><label class="lbl">JWT 过期时间 (小时)</label><input v-model.number="form.admin.jwt_expire_hours" type="number" class="ipt" /></div>
      </div>
    </section>

    <!-- OpenAI 配置 -->
    <section class="card">
      <h2 class="card-title">OpenAI 配置</h2>
      <div class="grid gap-3 md:grid-cols-2">
        <div>
          <label class="lbl">API 地址</label><input v-model="form.openai.base_url" class="ipt" />
          <p class="hint">上游 API Base URL</p>
        </div>
        <div><label class="lbl">Auth 地址</label><input v-model="form.openai.auth_url" class="ipt" /></div>
        <div><label class="lbl">Authorize 地址</label><input v-model="form.openai.authorize_url" class="ipt" /></div>
        <div><label class="lbl">Token 地址</label><input v-model="form.openai.token_url" class="ipt" /></div>
        <div><label class="lbl">注册回调地址</label><input v-model="form.openai.register_callback_url" class="ipt" /></div>
        <div>
          <label class="lbl">OAuth Client ID</label><input v-model="form.openai.oauth_client_id" class="ipt" />
          <p class="hint">抓包获取</p>
        </div>
        <div>
          <label class="lbl">OAuth Client Secret</label><input v-model="form.openai.oauth_client_secret" type="password" class="ipt" />
          <p class="hint">抓包获取</p>
        </div>
        <div>
          <label class="lbl">Turnstile Site Key</label><input v-model="form.openai.turnstile_sitekey" class="ipt" />
          <p class="hint">Cloudflare 人机验证 sitekey</p>
        </div>
        <div>
          <label class="lbl">注册默认密码</label><input v-model="form.openai.default_password" type="password" class="ipt" />
          <p class="hint">批量注册 OpenAI 账号使用</p>
        </div>
        <div><label class="lbl">请求超时 (秒)</label><input v-model.number="form.openai.timeout_seconds" type="number" class="ipt" /></div>
        <div><label class="lbl">流式超时 (秒)</label><input v-model.number="form.openai.stream_timeout_seconds" type="number" class="ipt" /></div>
      </div>
    </section>

    <!-- TalentMail -->
    <section class="card">
      <h2 class="card-title">TalentMail 邮件服务</h2>
      <div class="grid gap-3 md:grid-cols-2">
        <div class="md:col-span-2"><label class="lbl">API 地址</label><input v-model="form.talentmail.base_url" class="ipt" /></div>
        <div><label class="lbl">登录邮箱</label><input v-model="form.talentmail.email" class="ipt" /></div>
        <div><label class="lbl">登录密码</label><input v-model="form.talentmail.password" type="password" class="ipt" /></div>
      </div>
    </section>

    <!-- 注册设置 -->
    <section class="card">
      <h2 class="card-title">注册设置</h2>
      <div class="grid gap-3 md:grid-cols-2">
        <div><label class="lbl">资料名称</label><input v-model="form.registration.profile_name" class="ipt" /></div>
        <div><label class="lbl">最大并发注册数</label><input v-model.number="form.registration.max_concurrent_registrations" type="number" class="ipt" /></div>
        <label class="toggle"><input type="checkbox" v-model="form.registration.skip_phone_verification" class="toggle-cb" /><span class="toggle-track" /><span>跳过手机验证</span></label>
        <label class="toggle"><input type="checkbox" v-model="form.registration.skip_upgrade_plus" class="toggle-cb" /><span class="toggle-track" /><span>跳过升级 Plus</span></label>
      </div>
      <h3 class="mt-4 mb-2 text-sm font-medium text-slate-500 dark:text-slate-400">浏览器自动化 (Playwright)</h3>
      <div class="grid gap-3 md:grid-cols-2">
        <label class="toggle"><input type="checkbox" v-model="form.registration.headless" class="toggle-cb" /><span class="toggle-track" /><span>无头模式</span></label>
        <div><label class="lbl">CF 等待超时 (秒)</label><input v-model.number="form.registration.browser_timeout" type="number" class="ipt" /><p class="hint">Cloudflare 验证等待超时</p></div>
        <div><label class="lbl">打字间隔 (毫秒)</label><input v-model.number="form.registration.typing_delay_ms" type="number" class="ipt" /><p class="hint">模拟真人打字速度</p></div>
        <div><label class="lbl">页面跳转超时 (秒)</label><input v-model.number="form.registration.navigation_timeout" type="number" class="ipt" /><p class="hint">等待 OAuth 回调跳转</p></div>
      </div>
    </section>

    <!-- 代理池设置 -->
    <section class="card">
      <h2 class="card-title">代理池设置</h2>
      <div class="grid gap-3 md:grid-cols-3">
        <div><label class="lbl">冷却时间 (秒)</label><input v-model.number="form.proxy.cooldown_seconds" type="number" class="ipt" /></div>
        <div><label class="lbl">失败阈值</label><input v-model.number="form.proxy.failure_threshold" type="number" class="ipt" /></div>
        <div><label class="lbl">健康检查间隔 (秒)</label><input v-model.number="form.proxy.health_check_interval_seconds" type="number" class="ipt" /></div>
      </div>
      <h3 class="mt-4 mb-2 text-sm font-medium text-slate-500 dark:text-slate-400">Token 自动刷新</h3>
      <div class="grid gap-3 md:grid-cols-3">
        <label class="toggle md:col-span-3"><input type="checkbox" v-model="form.proxy.token_refresh_enabled" class="toggle-cb" /><span class="toggle-track" /><span>启用自动刷新</span></label>
        <div><label class="lbl">刷新间隔 (秒)</label><input v-model.number="form.proxy.token_refresh_interval_seconds" type="number" class="ipt" /></div>
        <div><label class="lbl">提前刷新 (秒)</label><input v-model.number="form.proxy.token_refresh_skew_seconds" type="number" class="ipt" /></div>
        <div><label class="lbl">刷新超时 (秒)</label><input v-model.number="form.proxy.token_refresh_timeout_seconds" type="number" class="ipt" /></div>
        <div><label class="lbl">最大重试次数</label><input v-model.number="form.proxy.token_refresh_max_retries" type="number" class="ipt" /></div>
        <div><label class="lbl">退避间隔 (秒)</label><input v-model.number="form.proxy.token_refresh_backoff_seconds" type="number" class="ipt" /></div>
      </div>
    </section>

    <!-- 网络代理 -->
    <section class="card">
      <h2 class="card-title">网络代理</h2>
      <div class="space-y-3">
        <div>
          <label class="lbl">全局代理</label><input v-model="form.network.http_proxy" class="ipt" />
          <p class="hint">如 socks5://127.0.0.1:7897 或 http://proxy:8080</p>
        </div>
        <div>
          <label class="lbl">OpenAI 专用代理</label><input v-model="form.network.openai_proxy" class="ipt" />
          <p class="hint">优先于全局代理，留空则使用全局</p>
        </div>
        <div>
          <label class="lbl">TalentMail 专用代理</label><input v-model="form.network.talentmail_proxy" class="ipt" />
          <p class="hint">优先于全局代理，留空则使用全局</p>
        </div>
      </div>
    </section>

    <!-- 存储配置 -->
    <section class="card">
      <h2 class="card-title">存储配置</h2>
      <div class="grid gap-3 md:grid-cols-2">
        <div><label class="lbl">账号数据库路径</label><input v-model="form.storage.db_path" class="ipt" /></div>
        <div><label class="lbl">令牌数据库路径</label><input v-model="form.storage.tokens_db_path" class="ipt" /></div>
        <div><label class="lbl">统计数据库路径</label><input v-model="form.storage.stats_db_path" class="ipt" /></div>
        <div>
          <label class="lbl">加密密钥</label><input v-model="form.storage.encryption_key" type="password" class="ipt" />
          <p class="hint">首次启动自动生成</p>
        </div>
      </div>
    </section>

    <!-- 日志配置 -->
    <section class="card">
      <h2 class="card-title">日志配置</h2>
      <div class="grid gap-3 md:grid-cols-2">
        <div>
          <label class="lbl">日志级别</label>
          <select v-model="form.logging.level" class="ipt">
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>
        <div>
          <label class="lbl">日志格式</label>
          <select v-model="form.logging.format" class="ipt">
            <option value="json">JSON</option>
            <option value="text">纯文本</option>
          </select>
        </div>
      </div>
    </section>

    <!-- 操作按钮 -->
    <div class="flex justify-end gap-3">
      <button type="button" class="btn-secondary" @click="onReset">重置</button>
      <button type="button" class="btn-primary" :disabled="store.saving" @click="onSave">
        {{ store.saving ? '保存中...' : '保存配置' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { type AppConfig, defaultConfig, useConfigStore } from '@/stores/config'

const store = useConfigStore()
const saved = ref(false)
const form = reactive<AppConfig>(structuredClone(defaultConfig))

function syncForm(config: AppConfig) {
  const next = structuredClone(config)
  Object.assign(form.admin, next.admin)
  Object.assign(form.openai, next.openai)
  Object.assign(form.talentmail, next.talentmail)
  Object.assign(form.registration, next.registration)
  Object.assign(form.proxy, next.proxy)
  Object.assign(form.network, next.network)
  Object.assign(form.storage, next.storage)
  Object.assign(form.logging, next.logging)
}

async function onSave() {
  saved.value = false
  try {
    const savedConfig = await store.saveConfig(structuredClone(form) as AppConfig)
    syncForm(savedConfig)
    saved.value = true
    window.setTimeout(() => { saved.value = false }, 3000)
  } catch {
    // store.error handles display
  }
}

function onReset() {
  syncForm(store.config)
}

onMounted(async () => {
  try {
    await store.fetchConfig()
    syncForm(store.config)
  } catch {
    // store.error handles display
  }
})
</script>

<style scoped>
.card {
  @apply rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700;
}
.card-title {
  @apply mb-4 text-lg font-semibold text-slate-900 dark:text-slate-200;
}
.lbl {
  @apply mb-1 block text-sm font-medium text-slate-600 dark:text-slate-400;
}
.ipt {
  @apply w-full rounded-lg border border-slate-300 px-3 py-2 text-sm
    focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
    dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200;
}
.hint {
  @apply mt-0.5 text-xs text-slate-400 dark:text-slate-500;
}
.msg {
  @apply rounded-lg border px-4 py-3 text-sm;
}
.msg-error {
  @apply border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-900/30 dark:text-rose-300;
}
.msg-ok {
  @apply border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300;
}
.btn-primary {
  @apply rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60;
}
.btn-secondary {
  @apply rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50
    dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700;
}

/* Toggle switch */
.toggle {
  @apply flex cursor-pointer items-center gap-2.5 py-1 text-sm text-slate-700 dark:text-slate-300;
}
.toggle-cb {
  @apply sr-only;
}
.toggle-track {
  @apply relative inline-block h-5 w-9 shrink-0 rounded-full bg-slate-300 transition-colors dark:bg-slate-600;
}
.toggle-track::after {
  content: '';
  @apply absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform;
}
.toggle-cb:checked + .toggle-track {
  @apply bg-blue-600;
}
.toggle-cb:checked + .toggle-track::after {
  @apply translate-x-4;
}
</style>
