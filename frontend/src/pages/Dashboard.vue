<template>
  <div class="space-y-6">
    <p v-if="store.error" class="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
      {{ store.error }}
    </p>

    <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
      <StatCard label="总账号" :value="store.stats.accounts.total">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </template>
      </StatCard>

      <StatCard label="活跃" :value="store.stats.accounts.active" value-class="text-green-500" icon-bg-class="bg-green-100 text-green-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <polyline stroke-linecap="round" stroke-linejoin="round" points="20 6 9 17 4 12" />
          </svg>
        </template>
      </StatCard>

      <StatCard label="冷却中" :value="store.stats.accounts.cooling" value-class="text-amber-500" icon-bg-class="bg-amber-100 text-amber-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <circle cx="12" cy="12" r="10" />
            <polyline stroke-linecap="round" stroke-linejoin="round" points="12 6 12 12 16 14" />
          </svg>
        </template>
      </StatCard>

      <StatCard label="已封禁" :value="store.stats.accounts.banned" value-class="text-red-500" icon-bg-class="bg-red-100 text-red-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <circle cx="12" cy="12" r="10" />
            <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
          </svg>
        </template>
      </StatCard>

      <StatCard label="已过期" :value="store.stats.accounts.expired" value-class="text-slate-500" icon-bg-class="bg-slate-200 text-slate-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </template>
      </StatCard>

      <StatCard
        label="已废弃"
        :value="store.stats.accounts.abandoned"
        value-class="text-red-500"
        icon-bg-class="bg-red-100 text-red-600"
        card-class="ring-red-200"
      >
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <polyline stroke-linecap="round" stroke-linejoin="round" points="3 6 5 6 21 6" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 6l-1 14H6L5 6m3 0V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
          </svg>
        </template>
      </StatCard>
    </section>

    <section class="grid gap-4 md:grid-cols-5">
      <StatCard label="今日请求" :value="store.stats.usage.today_requests" value-class="text-blue-500" icon-bg-class="bg-blue-100 text-blue-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 12h16" />
            <path stroke-linecap="round" stroke-linejoin="round" d="m13 5 7 7-7 7" />
          </svg>
        </template>
      </StatCard>
      <StatCard label="今日TOKEN" :value="formattedTokens" value-class="text-blue-500" icon-bg-class="bg-blue-100 text-blue-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h8" />
          </svg>
        </template>
      </StatCard>
      <StatCard label="当前RPM" :value="store.stats.usage.current_rpm" value-class="text-blue-500" icon-bg-class="bg-blue-100 text-blue-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <circle cx="12" cy="12" r="9" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 7v5l3 3" />
          </svg>
        </template>
      </StatCard>
      <StatCard label="当前TPM" :value="formattedCurrentTpm" value-class="text-blue-500" icon-bg-class="bg-blue-100 text-blue-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v18" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M7 8h8a3 3 0 1 1 0 6H9a3 3 0 1 0 0 6h8" />
          </svg>
        </template>
      </StatCard>
      <StatCard label="成功率" :value="formattedSuccessRate" value-class="text-blue-500" icon-bg-class="bg-blue-100 text-blue-600">
        <template #icon>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </template>
      </StatCard>
    </section>

    <section class="grid gap-4 lg:grid-cols-2">
      <ModelList :models="store.stats.models" />
      <ServiceStatus
        :uptime-seconds="store.stats.service.uptime_seconds"
        :python-version="store.stats.service.python_version"
        :schedule-mode="store.stats.service.schedule_mode"
        :version="store.stats.service.version"
        :upstream-status="store.stats.service.upstream_status"
        :openai-base-url="store.stats.service.openai_base_url"
        :chat2api-mode="store.stats.service.chat2api_mode"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import ModelList from '@/components/ModelList.vue'
import ServiceStatus from '@/components/ServiceStatus.vue'
import StatCard from '@/components/StatCard.vue'
import { useDashboardStore } from '@/stores/dashboard'

const store = useDashboardStore()

const formattedTokens = computed(() => formatTokenCount(Number(store.stats.usage.today_tokens ?? 0)))
const formattedCurrentTpm = computed(() => formatTokenCount(Number(store.stats.usage.current_tpm ?? 0)))
const formattedSuccessRate = computed(() => `${Number(store.stats.usage.success_rate ?? 0).toFixed(2)}%`)

function formatTokenCount(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`
  }
  return String(value)
}

onMounted(async () => {
  try {
    await store.fetchStats()
  } catch {
    // Error state is already handled in store.error for UI display.
  }
})
</script>
