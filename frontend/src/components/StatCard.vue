<template>
  <section class="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700" :class="props.cardClass">
    <div class="mb-3 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
      <div class="flex h-8 w-8 items-center justify-center rounded-full" :class="props.iconBgClass">
        <slot name="icon" />
      </div>
      <span>{{ props.label }}</span>
    </div>
    <div class="tabular-nums text-3xl font-semibold" :class="props.valueClass">{{ props.value }}</div>
  </section>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label: string
    value: string | number
    iconBgClass?: string
    valueClass?: string
    cardClass?: string
  }>(),
  {
    iconBgClass: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300',
    valueClass: 'text-slate-900 dark:text-slate-200',
    cardClass: ''
  }
)
</script>
