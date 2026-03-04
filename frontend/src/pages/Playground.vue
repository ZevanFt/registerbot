<template>
  <div class="flex h-[calc(100vh-7rem)] flex-col">
    <!-- Top bar: model + token selector -->
    <div class="mb-3 flex items-center gap-3 rounded-xl bg-white p-3 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex items-center gap-2">
        <label class="text-sm font-medium text-slate-600 dark:text-slate-400">模型</label>
        <select v-model="selectedModel" class="sel">
          <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
      <div class="flex items-center gap-2">
        <label class="text-sm font-medium text-slate-600 dark:text-slate-400">令牌</label>
        <select v-model="selectedTokenKey" class="sel">
          <option v-for="t in tokens" :key="t.id" :value="t.key">{{ t.name }} ({{ t.key.slice(0, 8) }}...)</option>
        </select>
      </div>
      <button type="button" class="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700" @click="clearChat">
        清空对话
      </button>
    </div>

    <!-- Messages area -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div v-if="messages.length === 0 && !streamingContent" class="flex h-full items-center justify-center text-sm text-slate-400 dark:text-slate-500">
        发送消息开始对话...
      </div>
      <div v-for="(msg, idx) in messages" :key="idx" class="mb-4 last:mb-0">
        <div class="mb-1 text-xs font-medium" :class="msg.role === 'user' ? 'text-blue-600 dark:text-blue-400' : 'text-emerald-600 dark:text-emerald-400'">
          {{ msg.role === 'user' ? '你' : 'AI' }}
        </div>
        <div class="whitespace-pre-wrap rounded-lg px-3 py-2 text-sm leading-relaxed" :class="msg.role === 'user' ? 'bg-blue-50 text-slate-800 dark:bg-blue-900/20 dark:text-slate-200' : 'bg-slate-50 text-slate-800 dark:bg-slate-700/50 dark:text-slate-200'">
          {{ msg.content }}
        </div>
      </div>
      <!-- Streaming response -->
      <div v-if="streamingContent !== null" class="mb-4">
        <div class="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">AI</div>
        <div class="whitespace-pre-wrap rounded-lg bg-slate-50 px-3 py-2 text-sm leading-relaxed text-slate-800 dark:bg-slate-700/50 dark:text-slate-200">
          {{ streamingContent }}<span v-if="loading" class="inline-block animate-pulse">▊</span>
        </div>
      </div>
      <!-- Loading placeholder (only when not streaming yet) -->
      <div v-else-if="loading" class="mb-4">
        <div class="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">AI</div>
        <div class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:bg-slate-700/50 dark:text-slate-400">
          <span class="inline-block animate-pulse">思考中...</span>
        </div>
      </div>
    </div>

    <!-- Input area -->
    <div class="mt-3 flex gap-2">
      <textarea
        ref="inputEl"
        v-model="inputText"
        class="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
        rows="2"
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
        :disabled="loading"
        @keydown.enter.exact.prevent="sendMessage"
      />
      <button
        type="button"
        class="shrink-0 rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="loading || !inputText.trim() || !selectedTokenKey"
        @click="sendMessage"
      >
        发送
      </button>
    </div>

    <!-- Error display -->
    <p v-if="error" class="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-900/30 dark:text-rose-300">
      {{ error }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { apiGet } from '@/api/client'

interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

interface TokenItem {
  id: number
  key: string
  name: string
  status: string
  is_active?: boolean
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001/api').replace(/\/api$/, '')

const models = ref<string[]>([])
const selectedModel = ref('')
const selectedTokenKey = ref('')
const tokens = ref<TokenItem[]>([])
const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const loading = ref(false)
const error = ref('')
const streamingContent = ref<string | null>(null)
const messagesContainer = ref<HTMLDivElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function loadTokens() {
  try {
    const data = await apiGet<TokenItem[]>('/tokens?reveal=true')
    const list = Array.isArray(data) ? data : ((data as Record<string, unknown>).tokens as TokenItem[] || [])
    tokens.value = list.filter((t: TokenItem) => t.is_active !== false && t.status !== 'inactive')
    if (tokens.value.length > 0 && !selectedTokenKey.value) {
      selectedTokenKey.value = tokens.value[0].key
    }
  } catch {
    // silently fail
  }
}

async function loadModels() {
  if (!selectedTokenKey.value) return
  try {
    const response = await fetch(`${API_BASE}/v1/models`, {
      headers: { Authorization: `Bearer ${selectedTokenKey.value}` },
    })
    if (response.ok) {
      const data = await response.json()
      const list: string[] = (data?.data || []).map((m: { id: string }) => m.id)
      models.value = list.length > 0 ? list : ['gpt-4o-mini']
      if (!selectedModel.value || !list.includes(selectedModel.value)) {
        selectedModel.value = models.value[0]
      }
    }
  } catch {
    if (models.value.length === 0) {
      models.value = ['gpt-4o-mini']
      selectedModel.value = 'gpt-4o-mini'
    }
  }
}

function clearChat() {
  messages.value = []
  error.value = ''
  streamingContent.value = null
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value || !selectedTokenKey.value) return

  error.value = ''
  messages.value = [...messages.value, { role: 'user', content: text }]
  inputText.value = ''
  loading.value = true
  streamingContent.value = null
  scrollToBottom()

  try {
    const response = await fetch(`${API_BASE}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${selectedTokenKey.value}`,
      },
      body: JSON.stringify({
        model: selectedModel.value,
        messages: messages.value.map((m) => ({ role: m.role, content: m.content })),
        stream: true,
      }),
    })

    if (!response.ok) {
      const errBody = await response.text()
      let errMsg = `HTTP ${response.status}`
      try {
        const parsed = JSON.parse(errBody)
        errMsg = parsed?.error?.message || errMsg
      } catch {
        errMsg = errBody || errMsg
      }
      error.value = errMsg
      loading.value = false
      return
    }

    // Stream SSE response
    const reader = response.body?.getReader()
    if (!reader) {
      error.value = '浏览器不支持流式读取'
      loading.value = false
      return
    }

    streamingContent.value = ''
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        const payload = trimmed.slice(6)
        if (payload === '[DONE]') continue

        try {
          const chunk = JSON.parse(payload)
          const delta = chunk?.choices?.[0]?.delta?.content
          if (delta) {
            streamingContent.value += delta
            scrollToBottom()
          }
        } catch {
          // skip malformed chunks
        }
      }
    }

    // Finalize: move streaming content into messages array
    const finalContent = streamingContent.value || '(无回复)'
    messages.value = [...messages.value, { role: 'assistant', content: finalContent }]
    streamingContent.value = null
    scrollToBottom()
  } catch (err) {
    // If we have partial streaming content, preserve it
    if (streamingContent.value) {
      messages.value = [...messages.value, { role: 'assistant', content: streamingContent.value }]
      streamingContent.value = null
    }
    error.value = err instanceof Error ? err.message : '请求失败'
  } finally {
    loading.value = false
    nextTick(() => inputEl.value?.focus())
  }
}

watch(selectedTokenKey, () => { loadModels() })

onMounted(async () => {
  await loadTokens()
  await loadModels()
  inputEl.value?.focus()
})
</script>

<style scoped>
.sel {
  @apply rounded-lg border border-slate-300 px-2 py-1.5 text-sm
    focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
    dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200;
}
</style>
