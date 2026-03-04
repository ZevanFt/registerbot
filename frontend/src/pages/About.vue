<template>
  <div class="mx-auto max-w-2xl space-y-6">
    <section class="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <div class="flex items-center gap-4">
        <div
          class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-cyan-400 text-xl font-bold text-white"
        >
          C
        </div>
        <div>
          <h2 class="text-xl font-semibold text-slate-900 dark:text-slate-100">codex2api</h2>
          <p class="text-sm text-slate-500 dark:text-slate-400">v0.1.0</p>
        </div>
      </div>

      <p class="mt-4 leading-relaxed text-slate-600 dark:text-slate-300">
        一个开源的 AI 模型 API 聚合管理工具，用于统一管理多个 AI
        服务账号，并将其转化为标准 OpenAI 兼容格式的 API
        接口，方便开发者在自己的项目中集成调用。
      </p>
    </section>

    <section class="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <h3 class="mb-3 text-base font-semibold text-slate-900 dark:text-slate-100">主要功能</h3>
      <ul class="space-y-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
        <li class="flex items-start gap-2">
          <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
          <span>多账号统一管理 — 集中维护多个 AI 服务的账号凭据与状态</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
          <span>API 令牌分发 — 生成独立访问令牌，支持按需分配与吊销</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
          <span>用量统计与日志 — 实时追踪请求次数、Token 消耗及调用明细</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
          <span>流水线自动化 — 基于可编排步骤的工作流引擎，简化重复操作</span>
        </li>
      </ul>
    </section>

    <section class="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <h3 class="mb-3 text-base font-semibold text-slate-900 dark:text-slate-100">作者</h3>
      <div class="flex items-center gap-3">
        <span
          class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300"
        >
          Z
        </span>
        <div>
          <p class="font-medium text-slate-900 dark:text-slate-100">Zevan</p>
          <p class="text-sm text-slate-500 dark:text-slate-400">独立开发者</p>
        </div>
      </div>
    </section>

    <section class="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700">
      <h3 class="mb-3 text-base font-semibold text-slate-900 dark:text-slate-100">免责声明</h3>
      <p class="text-sm leading-relaxed text-slate-500 dark:text-slate-400">
        本项目仅供学习与个人研究使用。用户应自行遵守所调用第三方服务的使用条款与相关法律法规。
        本项目不存储、转售或代理任何第三方服务，不对用户的使用行为承担责任。
        所有第三方产品名称、商标归其各自所有者所有，本项目与其无任何关联或背书关系。
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
</script>
