<template>
  <div class="flex h-[calc(100vh-7rem)] flex-col">
    <p v-if="notice" class="mb-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
      {{ notice }}
    </p>
    <div class="mb-3 rounded-xl bg-white p-3 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex flex-wrap items-center gap-2">
        <label class="text-sm font-medium text-slate-600 dark:text-slate-400">会话</label>
        <select v-model="activeSessionId" class="sel" @change="switchSession(activeSessionId)">
          <option v-for="s in filteredSessions" :key="s.id" :value="s.id">
            {{ s.pinned ? '📌 ' : '' }}[{{ s.tag }}] {{ s.title }}{{ s.archived ? '（归档）' : '' }}
          </option>
        </select>
        <input v-model.trim="sessionQuery" class="sel min-w-[12rem]" type="text" placeholder="搜索会话..." />
        <select v-model="sessionTagFilter" class="sel">
          <option value="all">全部标签</option>
          <option v-for="tag in SESSION_TAGS" :key="tag" :value="tag">{{ tag }}</option>
        </select>
        <label class="inline-flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
          <input v-model="showArchived" type="checkbox" />
          显示归档
        </label>

        <button type="button" class="msg-btn" :disabled="loading" @click="createSession">新建</button>
        <button type="button" class="msg-btn" :disabled="loading" @click="renameSession">重命名</button>
        <button type="button" class="msg-btn" :disabled="loading" @click="togglePinSession">
          {{ getActiveSession()?.pinned ? '取消置顶' : '置顶' }}
        </button>
        <button type="button" class="msg-btn" :disabled="loading" @click="setSessionTag">
          标签：{{ getActiveSession()?.tag ?? '测试' }}
        </button>
        <button type="button" class="msg-btn" :disabled="loading" @click="toggleArchiveSession">
          {{ getActiveSession()?.archived ? '恢复' : '归档' }}
        </button>
        <button type="button" class="msg-btn" :disabled="loading" @click="moveSession(-1)">上移</button>
        <button type="button" class="msg-btn" :disabled="loading" @click="moveSession(1)">下移</button>
        <button type="button" class="msg-btn" :disabled="loading || sessions.length === 0" @click="exportSessions">导出</button>
        <button type="button" class="msg-btn" :disabled="loading" @click="triggerImport">导入</button>
        <button type="button" class="msg-btn" :disabled="loading || sessions.length <= 1" @click="deleteSession">删除</button>
        <button type="button" class="msg-btn" :disabled="loading" @click="clearEmptySessions">清理空会话</button>
        <input ref="importFileInput" type="file" accept="application/json" class="hidden" @change="handleImport" />

        <div class="ml-auto flex flex-wrap items-center gap-2">
          <label class="text-sm font-medium text-slate-600 dark:text-slate-400">模型</label>
          <select v-model="selectedModel" class="sel">
            <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
          </select>
          <label class="text-sm font-medium text-slate-600 dark:text-slate-400">令牌</label>
          <select v-model="selectedTokenKey" class="sel">
            <option v-for="t in tokens" :key="t.id" :value="t.key">{{ t.name }} ({{ t.key.slice(0, 8) }}...)</option>
          </select>
          <button type="button" class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700" @click="clearChat">
            清空对话
          </button>
        </div>
      </div>

      <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600 sm:grid-cols-5 dark:text-slate-300">
        <div class="rounded-lg bg-slate-50 px-2 py-1 dark:bg-slate-700/60">总会话: {{ sessionStats.total }}</div>
        <div class="rounded-lg bg-slate-50 px-2 py-1 dark:bg-slate-700/60">活跃会话: {{ sessionStats.active }}</div>
        <div class="rounded-lg bg-slate-50 px-2 py-1 dark:bg-slate-700/60">归档会话: {{ sessionStats.archived }}</div>
        <div class="rounded-lg bg-slate-50 px-2 py-1 dark:bg-slate-700/60">总消息: {{ sessionStats.messages }}</div>
        <div class="rounded-lg bg-slate-50 px-2 py-1 dark:bg-slate-700/60">最近活跃: {{ sessionStats.lastActive }}</div>
      </div>
    </div>

    <div ref="messagesContainer" class="flex-1 overflow-y-auto rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div v-if="messages.length === 0 && !streamingContent" class="flex h-full items-center justify-center text-sm text-slate-400 dark:text-slate-500">
        发送消息开始对话...
      </div>

      <div v-for="(msg, idx) in messages" :key="msg.id" class="mb-4 last:mb-0">
        <div class="mb-1 text-xs font-medium" :class="msg.role === 'user' ? 'text-blue-600 dark:text-blue-400' : 'text-emerald-600 dark:text-emerald-400'">
          {{ msg.role === 'user' ? '你' : 'AI' }}
          <span class="ml-2 font-normal text-slate-400 dark:text-slate-500">{{ formatTs(msg.createdAt) }}</span>
        </div>

        <div class="rounded-lg px-3 py-2" :class="msg.role === 'user' ? 'bg-blue-50 text-slate-800 dark:bg-blue-900/20 dark:text-slate-200' : 'bg-slate-50 text-slate-800 dark:bg-slate-700/50 dark:text-slate-200'">
          <template v-if="editingMessageId === msg.id && msg.role === 'user'">
            <textarea v-model="editingText" class="w-full resize-y rounded-md border border-slate-300 bg-white p-2 text-sm leading-relaxed text-slate-800 focus:border-blue-500 focus:outline-none dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100" rows="3" />
            <div class="mt-2 flex items-center gap-2">
              <button type="button" class="msg-btn" @click="saveEdit(idx)">保存</button>
              <button type="button" class="msg-btn" @click="cancelEdit">取消</button>
            </div>
          </template>
          <template v-else>
            <div class="whitespace-pre-wrap text-sm leading-relaxed">{{ msg.content }}</div>
            <div class="mt-2 flex items-center gap-2">
              <button type="button" class="msg-btn" @click="copyMessage(msg.content)">复制</button>
              <button v-if="msg.role === 'assistant'" type="button" class="msg-btn" :disabled="loading" @click="regenerateAssistant(idx)">重新生成</button>
              <button v-if="msg.role === 'user'" type="button" class="msg-btn" :disabled="loading" @click="startEdit(msg)">编辑</button>
              <button type="button" class="msg-btn" :disabled="loading" @click="deleteMessage(idx)">删除</button>
            </div>
          </template>
        </div>
      </div>

      <div v-if="streamingContent !== null" class="mb-4">
        <div class="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">AI</div>
        <div class="whitespace-pre-wrap rounded-lg bg-slate-50 px-3 py-2 text-sm leading-relaxed text-slate-800 dark:bg-slate-700/50 dark:text-slate-200">
          {{ streamingContent }}<span v-if="loading" class="inline-block animate-pulse">▊</span>
        </div>
      </div>
      <div v-else-if="loading" class="mb-4">
        <div class="mb-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">AI</div>
        <div class="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:bg-slate-700/50 dark:text-slate-400">
          <span class="inline-block animate-pulse">思考中...</span>
        </div>
      </div>
    </div>

    <div class="mt-3 flex gap-2">
      <textarea
        ref="inputEl"
        v-model="inputText"
        class="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
        rows="2"
        placeholder="输入消息... (Enter / Ctrl+Enter / Cmd+Enter 发送, Shift+Enter 换行)"
        :disabled="loading"
        @keydown="handleInputKeydown"
      />
      <button type="button" class="shrink-0 rounded-xl bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60" :disabled="loading || !inputText.trim() || !selectedTokenKey" @click="sendMessage">
        发送
      </button>
    </div>

    <p v-if="error" class="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-900/30 dark:text-rose-300">
      {{ error }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { apiGet } from '@/api/client'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: string
}

interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  pinned: boolean
  archived: boolean
  autoTitle: boolean
  tag: SessionTag
  messages: ChatMessage[]
}

type SessionTag = '工作' | '生活' | '测试'

interface TokenItem {
  id: number
  key: string
  name: string
  status: string
  is_active?: boolean
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001/api').replace(/\/api$/, '')
const STORAGE_KEY = 'playground_chat_history_v1'
const SESSION_TAGS: SessionTag[] = ['工作', '生活', '测试']

const models = ref<string[]>([])
const selectedModel = ref('')
const selectedTokenKey = ref('')
const tokens = ref<TokenItem[]>([])

const sessions = ref<ChatSession[]>([])
const sessionQuery = ref('')
const sessionTagFilter = ref<'all' | SessionTag>('all')
const showArchived = ref(false)
const activeSessionId = ref('')
const messages = ref<ChatMessage[]>([])

const inputText = ref('')
const loading = ref(false)
const error = ref('')
const notice = ref('')
const streamingContent = ref<string | null>(null)
const editingMessageId = ref<string | null>(null)
const editingText = ref('')

const messagesContainer = ref<HTMLDivElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)
const importFileInput = ref<HTMLInputElement | null>(null)
let noticeTimer: number | null = null

function pushNotice(message: string) {
  notice.value = message
  if (noticeTimer !== null) window.clearTimeout(noticeTimer)
  noticeTimer = window.setTimeout(() => {
    notice.value = ''
    noticeTimer = null
  }, 2200)
}

function nowIso() {
  return new Date().toISOString()
}

function generateMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function generateSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function formatTs(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
}

function defaultSession(title = '新会话'): ChatSession {
  const now = nowIso()
  return {
    id: generateSessionId(),
    title,
    createdAt: now,
    updatedAt: now,
    pinned: false,
    archived: false,
    autoTitle: true,
    tag: '测试',
    messages: [],
  }
}

function orderedSessions(list: ChatSession[]) {
  const pinnedActive = list.filter((s) => s.pinned && !s.archived)
  const normalActive = list.filter((s) => !s.pinned && !s.archived)
  const pinnedArchived = list.filter((s) => s.pinned && s.archived)
  const normalArchived = list.filter((s) => !s.pinned && s.archived)
  return showArchived.value
    ? [...pinnedActive, ...normalActive, ...pinnedArchived, ...normalArchived]
    : [...pinnedActive, ...normalActive]
}

const filteredSessions = computed(() => {
  const query = sessionQuery.value.trim().toLowerCase()
  const ordered = orderedSessions(sessions.value)
  const byTag = sessionTagFilter.value === 'all'
    ? ordered
    : ordered.filter((s) => s.tag === sessionTagFilter.value)
  if (!query) return byTag
  const hit = byTag.filter((s) => s.title.toLowerCase().includes(query))
  if (hit.some((s) => s.id === activeSessionId.value)) return hit
  const active = ordered.find((s) => s.id === activeSessionId.value)
  return active ? [active, ...hit] : hit
})

const sessionStats = computed(() => {
  const total = sessions.value.length
  const archived = sessions.value.filter((s) => s.archived).length
  const active = total - archived
  const messages = sessions.value.reduce((sum, s) => sum + s.messages.length, 0)
  const last = [...sessions.value]
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0]
    ?.updatedAt
  return {
    total,
    archived,
    active,
    messages,
    lastActive: last ? formatTs(last) : '-',
  }
})

function getActiveSession() {
  return sessions.value.find((s) => s.id === activeSessionId.value)
}

function syncActiveSessionMessages() {
  const active = getActiveSession()
  if (!active) return
  active.messages = [...messages.value]
  active.updatedAt = nowIso()
}

function shortenTitle(raw: string) {
  const compact = raw.replace(/\s+/g, ' ').trim()
  if (!compact) return '新会话'
  return compact.length > 24 ? `${compact.slice(0, 24)}...` : compact
}

function maybeAutoRenameSessionByFirstUserMessage(content: string) {
  const active = getActiveSession()
  if (!active || !active.autoTitle) return
  const userCount = messages.value.filter((m) => m.role === 'user').length
  if (userCount > 1) return
  active.title = shortenTitle(content)
  active.updatedAt = nowIso()
}

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
    // ignore
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
  if (messages.value.length > 0 && !window.confirm('确认清空当前会话的全部消息吗？')) return
  messages.value = []
  error.value = ''
  streamingContent.value = null
  editingMessageId.value = null
  editingText.value = ''
  syncActiveSessionMessages()
  persistState()
}

async function requestAssistant(contextMessages: ChatMessage[], onFinalize: (text: string) => void) {
  try {
    const response = await fetch(`${API_BASE}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${selectedTokenKey.value}`,
      },
      body: JSON.stringify({
        model: selectedModel.value,
        messages: contextMessages.map((m) => ({ role: m.role, content: m.content })),
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
          // ignore malformed chunk
        }
      }
    }

    const finalContent = streamingContent.value || '(无回复)'
    onFinalize(finalContent)
    streamingContent.value = null
    syncActiveSessionMessages()
    persistState()
    scrollToBottom()
  } catch (err) {
    if (streamingContent.value) {
      messages.value = [
        ...messages.value,
        { id: generateMessageId(), role: 'assistant', content: streamingContent.value, createdAt: nowIso() },
      ]
      streamingContent.value = null
      syncActiveSessionMessages()
      persistState()
    }
    error.value = err instanceof Error ? err.message : '请求失败'
  } finally {
    loading.value = false
    nextTick(() => inputEl.value?.focus())
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value || !selectedTokenKey.value) return

  error.value = ''
  const userMessage: ChatMessage = { id: generateMessageId(), role: 'user', content: text, createdAt: nowIso() }
  messages.value = [...messages.value, userMessage]
  maybeAutoRenameSessionByFirstUserMessage(text)
  inputText.value = ''
  loading.value = true
  streamingContent.value = null
  syncActiveSessionMessages()
  persistState()
  scrollToBottom()

  await requestAssistant(messages.value, (finalContent) => {
    messages.value = [
      ...messages.value,
      { id: generateMessageId(), role: 'assistant', content: finalContent, createdAt: nowIso() },
    ]
  })
}

function handleInputKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  event.preventDefault()
  if (loading.value) return
  void sendMessage()
}

function startEdit(msg: ChatMessage) {
  editingMessageId.value = msg.id
  editingText.value = msg.content
}

function cancelEdit() {
  editingMessageId.value = null
  editingText.value = ''
}

function saveEdit(index: number) {
  const content = editingText.value.trim()
  if (!content) return
  const next = [...messages.value]
  next[index] = { ...next[index], content }
  messages.value = next.slice(0, index + 1)
  cancelEdit()
  syncActiveSessionMessages()
  persistState()
}

function deleteMessage(index: number) {
  if (index < 0 || index >= messages.value.length) return
  if (!window.confirm('确认删除该消息及其后续上下文吗？')) return
  messages.value = messages.value.slice(0, index)
  cancelEdit()
  syncActiveSessionMessages()
  persistState()
}

async function regenerateAssistant(index: number) {
  if (loading.value) return
  const target = messages.value[index]
  if (!target || target.role !== 'assistant') return
  const context = messages.value.slice(0, index)
  if (context.length === 0 || context[context.length - 1]?.role !== 'user') {
    error.value = '只能重新生成紧跟用户消息的 AI 回复'
    return
  }

  error.value = ''
  messages.value = context
  loading.value = true
  streamingContent.value = null
  syncActiveSessionMessages()
  persistState()
  scrollToBottom()

  await requestAssistant(context, (finalContent) => {
    messages.value = [
      ...context,
      { id: generateMessageId(), role: 'assistant', content: finalContent, createdAt: nowIso() },
    ]
  })
}

async function copyMessage(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    pushNotice('内容已复制')
  } catch {
    error.value = '复制失败，请检查浏览器剪贴板权限'
  }
}

function persistState() {
  const payload = {
    selectedModel: selectedModel.value,
    selectedTokenKey: selectedTokenKey.value,
    sessions: sessions.value,
    activeSessionId: activeSessionId.value,
    showArchived: showArchived.value,
    sessionTagFilter: sessionTagFilter.value,
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

function sanitizeMessages(list: unknown): ChatMessage[] {
  if (!Array.isArray(list)) return []
  return list
    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
    .map((item) => ({
      id: typeof item.id === 'string' ? item.id : generateMessageId(),
      role: item.role === 'assistant' || item.role === 'system' ? item.role : 'user',
      content: typeof item.content === 'string' ? item.content : '',
      createdAt: typeof item.createdAt === 'string' ? item.createdAt : nowIso(),
    }))
}

function sanitizeSession(session: Partial<ChatSession>): ChatSession {
  const title = typeof session.title === 'string' && session.title.trim() ? session.title : '未命名会话'
  const tag: SessionTag = SESSION_TAGS.includes(session.tag as SessionTag) ? (session.tag as SessionTag) : '测试'
  return {
    id: typeof session.id === 'string' ? session.id : generateSessionId(),
    title,
    createdAt: typeof session.createdAt === 'string' ? session.createdAt : nowIso(),
    updatedAt: typeof session.updatedAt === 'string' ? session.updatedAt : nowIso(),
    pinned: Boolean(session.pinned),
    archived: Boolean(session.archived),
    autoTitle:
      typeof session.autoTitle === 'boolean'
        ? session.autoTitle
        : /^会话\s*\d+$/.test(title) || title === '新会话',
    tag,
    messages: sanitizeMessages(session.messages),
  }
}

function isSessionEmpty(session: ChatSession) {
  if (session.messages.length === 0) return true
  return session.messages.every((m) => !m.content.trim())
}

function restoreState() {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw) as {
      selectedModel?: string
      selectedTokenKey?: string
      sessions?: ChatSession[]
      activeSessionId?: string
      messages?: ChatMessage[]
      showArchived?: boolean
      sessionTagFilter?: 'all' | SessionTag
    }

    if (Array.isArray(parsed.sessions) && parsed.sessions.length > 0) {
      sessions.value = parsed.sessions.map((s) => sanitizeSession(s))
    } else {
      const fallback = defaultSession('会话 1')
      fallback.messages = sanitizeMessages(parsed.messages)
      sessions.value = [fallback]
    }

    activeSessionId.value =
      typeof parsed.activeSessionId === 'string' && sessions.value.some((s) => s.id === parsed.activeSessionId)
        ? parsed.activeSessionId
        : sessions.value[0].id

    messages.value = [...(getActiveSession()?.messages || [])]
    if (typeof parsed.selectedTokenKey === 'string') selectedTokenKey.value = parsed.selectedTokenKey
    if (typeof parsed.selectedModel === 'string') selectedModel.value = parsed.selectedModel
    if (typeof parsed.showArchived === 'boolean') showArchived.value = parsed.showArchived
    if (parsed.sessionTagFilter === 'all' || SESSION_TAGS.includes(parsed.sessionTagFilter as SessionTag)) {
      sessionTagFilter.value = parsed.sessionTagFilter as 'all' | SessionTag
    }
  } catch {
    // ignore malformed history
  }
}

function createSession() {
  const session = defaultSession(`会话 ${sessions.value.length + 1}`)
  sessions.value = [session, ...sessions.value]
  activeSessionId.value = session.id
  messages.value = []
  cancelEdit()
  persistState()
  pushNotice('已新建会话')
}

function switchSession(sessionId: string) {
  const target = sessions.value.find((s) => s.id === sessionId)
  if (!target) return
  activeSessionId.value = target.id
  messages.value = [...target.messages]
  cancelEdit()
  persistState()
  scrollToBottom()
}

function renameSession() {
  const active = getActiveSession()
  if (!active) return
  const name = window.prompt('输入会话名称', active.title)?.trim()
  if (!name) return
  active.title = name
  active.autoTitle = false
  active.updatedAt = nowIso()
  persistState()
  pushNotice('会话名称已更新')
}

function togglePinSession() {
  const active = getActiveSession()
  if (!active) return
  active.pinned = !active.pinned
  active.updatedAt = nowIso()
  persistState()
  pushNotice(active.pinned ? '会话已置顶' : '会话已取消置顶')
}

function setSessionTag() {
  const active = getActiveSession()
  if (!active) return
  const current = active.tag
  const input = window.prompt(`输入标签（${SESSION_TAGS.join('/')}）`, current)?.trim()
  if (!input) return
  if (!SESSION_TAGS.includes(input as SessionTag)) {
    error.value = `标签仅支持：${SESSION_TAGS.join('/')}`
    return
  }
  active.tag = input as SessionTag
  active.updatedAt = nowIso()
  persistState()
  pushNotice(`标签已更新为：${active.tag}`)
}

function toggleArchiveSession() {
  const active = getActiveSession()
  if (!active) return
  active.archived = !active.archived
  active.updatedAt = nowIso()
  if (active.archived && !showArchived.value) {
    const next = orderedSessions(sessions.value).find((s) => !s.archived && s.id !== active.id)
    if (next) {
      activeSessionId.value = next.id
      messages.value = [...next.messages]
    }
  }
  persistState()
  pushNotice(active.archived ? '会话已归档' : '会话已恢复')
}

function moveSession(direction: -1 | 1) {
  const active = getActiveSession()
  if (!active) return
  const group = sessions.value.filter((s) => s.archived === active.archived && s.pinned === active.pinned)
  const groupIdx = group.findIndex((s) => s.id === active.id)
  const targetIdx = groupIdx + direction
  if (groupIdx < 0 || targetIdx < 0 || targetIdx >= group.length) return

  const target = group[targetIdx]
  const aIdx = sessions.value.findIndex((s) => s.id === active.id)
  const bIdx = sessions.value.findIndex((s) => s.id === target.id)
  if (aIdx < 0 || bIdx < 0) return
  const next = [...sessions.value]
  ;[next[aIdx], next[bIdx]] = [next[bIdx], next[aIdx]]
  sessions.value = next
  persistState()
  pushNotice(direction < 0 ? '会话已上移' : '会话已下移')
}

function clearEmptySessions() {
  const emptyCount = sessions.value.filter((s) => isSessionEmpty(s)).length
  if (emptyCount === 0) {
    error.value = '没有可清理的空会话'
    return
  }
  const ok = window.confirm(`确认清理 ${emptyCount} 个空会话吗？`)
  if (!ok) return

  const activeId = activeSessionId.value
  sessions.value = sessions.value.filter((s) => !isSessionEmpty(s))
  if (sessions.value.length === 0) {
    const session = defaultSession('会话 1')
    sessions.value = [session]
    activeSessionId.value = session.id
    messages.value = []
    persistState()
    pushNotice(`已清理 ${emptyCount} 个空会话`)
    return
  }

  const stillHasActive = sessions.value.some((s) => s.id === activeId)
  if (!stillHasActive) {
    const next = orderedSessions(sessions.value)[0]
    if (next) {
      activeSessionId.value = next.id
      messages.value = [...next.messages]
    }
  } else {
    activeSessionId.value = activeId
    messages.value = [...(getActiveSession()?.messages || [])]
  }
  persistState()
  pushNotice(`已清理 ${emptyCount} 个空会话`)
}

function deleteSession() {
  if (!window.confirm('确认删除当前会话吗？该操作不可撤销。')) return
  if (sessions.value.length <= 1) {
    clearChat()
    return
  }
  const idx = sessions.value.findIndex((s) => s.id === activeSessionId.value)
  if (idx < 0) return
  sessions.value.splice(idx, 1)
  const next = orderedSessions(sessions.value)[0]
  if (next) {
    activeSessionId.value = next.id
    messages.value = [...next.messages]
  }
  cancelEdit()
  persistState()
  pushNotice('会话已删除')
}

function exportSessions() {
  const payload = {
    exportedAt: nowIso(),
    selectedModel: selectedModel.value,
    selectedTokenKey: selectedTokenKey.value,
    activeSessionId: activeSessionId.value,
    showArchived: showArchived.value,
    sessions: sessions.value,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `playground-sessions-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  pushNotice('会话已导出')
}

function triggerImport() {
  importFileInput.value?.click()
}

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const parsed = JSON.parse(text) as {
      sessions?: ChatSession[]
      activeSessionId?: string
      selectedModel?: string
      selectedTokenKey?: string
      showArchived?: boolean
    }
    const imported = Array.isArray(parsed.sessions) ? parsed.sessions.map((s) => sanitizeSession(s)) : []
    if (imported.length === 0) {
      error.value = '导入失败：文件中没有有效会话'
      return
    }
    sessions.value = imported
    activeSessionId.value =
      typeof parsed.activeSessionId === 'string' && sessions.value.some((s) => s.id === parsed.activeSessionId)
        ? parsed.activeSessionId
        : orderedSessions(sessions.value)[0].id
    messages.value = [...(getActiveSession()?.messages || [])]
    if (typeof parsed.selectedModel === 'string') selectedModel.value = parsed.selectedModel
    if (typeof parsed.selectedTokenKey === 'string') selectedTokenKey.value = parsed.selectedTokenKey
    if (typeof parsed.showArchived === 'boolean') showArchived.value = parsed.showArchived
    cancelEdit()
    persistState()
    scrollToBottom()
    pushNotice(`已导入 ${imported.length} 个会话`)
  } catch {
    error.value = '导入失败：JSON 格式无效'
  } finally {
    if (input) input.value = ''
  }
}

watch(selectedTokenKey, () => {
  void loadModels()
})

watch([selectedModel, selectedTokenKey, showArchived], () => {
  persistState()
})
watch(sessionTagFilter, () => {
  persistState()
})

onMounted(async () => {
  restoreState()
  if (sessions.value.length === 0) {
    const session = defaultSession('会话 1')
    sessions.value = [session]
    activeSessionId.value = session.id
  }
  if (!activeSessionId.value) {
    activeSessionId.value = orderedSessions(sessions.value)[0].id
  }
  if (messages.value.length === 0) {
    messages.value = [...(getActiveSession()?.messages || [])]
  }

  await loadTokens()
  await loadModels()
  syncActiveSessionMessages()
  persistState()
  scrollToBottom()
  inputEl.value?.focus()
})
</script>

<style scoped>
.sel {
  @apply rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200;
}

.msg-btn {
  @apply rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-600/70;
}
</style>
