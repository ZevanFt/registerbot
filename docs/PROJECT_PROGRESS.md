# codex2api - 项目进度文档

> 最后更新: 2026-03-06

## 最新修复 (2026-03-05)

### 注册预检失败根因核实与恢复 ✅ (2026-03-06)

- 用户反馈“生日未选导致失败”已核实：
  - 浏览器链路日志显示 `about_you_birthday_filled`，随机生日范围已满足 20-50 岁成人条件
  - 本次成功样例生日日志：`November 18, 1983`（`mode=spinbutton`）
- `authorization_code missing in context` 高频失败的直接原因已定位：
  - 8001 端口长期被旧 backend 进程占用
  - 重启脚本启动的新进程未成功绑定，导致实际请求仍命中旧代码
- 处理后结果：
  - 替换 8001 占用进程后，`scripts/register_batch.py --target 1 --max-failures 1` 通过
  - 成功注册并入库 `f97orz7c@talenting.vip`，流水线耗时约 `160.08s`

### 批量注册容量验证（目标 10 账号）✅ (2026-03-06)

- 分两阶段执行：
  - 阶段1：`--target 3`，结果 `3/3` 成功
  - 阶段2：`--target 5`，结果 `5` 成功 / `1` 失败（邮箱验证码超时，自动继续后补齐）
- 关键失败样例：
  - `TimeoutError: Timed out waiting verification code for mailbox: 82`
  - 属于 TalentMail 到码延迟，不是 about-you 生日步骤失败
- 最终结果：
  - 批量脚本汇总 `accounts_total_now=10`
  - 结果日志：`.run/register-batch-20260306-014950.log`

### 账号池轮转修复（新账号不被使用）✅ (2026-03-06)

- 现象：
  - 抽检对话全部命中 `account_id=5`，新注册账号未参与请求分配。
- 根因：
  - `AccountPool` 只选择 `status=active` 账号；
  - 注册流水线落库状态是 `status=registered`。
- 修复：
  - `RegistrationService.save_account` 改为保存 `status=active`；
  - 已有 `registered` 账号批量迁移为 `active`；
  - 对应测试用例同步更新并通过。
- 验证：
  - 连续 6 次 `/v1/chat/completions` 后，`usage_logs` 最新 `account_id` 为 `14,13,12,11,10,9`，确认轮转生效。

### 操练场交互增强与历史持久化 ✅ (2026-03-06)

- 新增对话操作按钮：
  - 每条消息：`复制`
  - AI 消息：`重新生成`
  - 用户消息：`编辑`（保存后自动截断后续上下文，避免脏上下文）
- 新增历史持久化：
  - `selectedModel`、`selectedTokenKey`、`messages` 保存到 `localStorage`
  - 页面刷新后自动恢复会话
- 兼容性与质量：
  - 保持流式 SSE 输出
  - 前端类型检查通过：`npm run type-check`

### 操练场多会话与时间戳 ✅ (2026-03-06)

- 新增会话管理能力：
  - 会话下拉切换
  - `新建 / 重命名 / 删除` 会话按钮
  - 会话间消息隔离保存
- 新增消息时间戳：
  - 用户与 AI 消息展示创建时间
- 兼容性：
  - 对旧版 `localStorage` 结构做向后兼容迁移
  - 继续支持复制、重新生成、编辑功能与流式输出
  - 前端类型检查通过：`npm run type-check`

### 操练场进一步增强（搜索/置顶/单条删除）✅ (2026-03-06)

- 新增会话搜索：
  - 按会话标题实时过滤会话列表
- 新增会话置顶：
  - 支持置顶/取消置顶
  - 列表按“置顶优先 + 最近更新时间”排序
- 新增单条消息删除：
  - 提供 `删除` 按钮
  - 为避免上下文污染，删除采用“从该消息起截断后续消息”的安全策略
- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 操练场导入导出与防误删 ✅ (2026-03-06)

- 新增会话导出：
  - 一键导出全部会话为 JSON
- 新增会话导入：
  - 支持从 JSON 导入会话并做结构清洗
  - 自动兼容字段缺失与旧结构
- 防误删确认：
  - 清空当前会话前确认
  - 删除消息链前确认
  - 删除会话前确认
- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 操练场自动命名与快捷键 ✅ (2026-03-06)

- 会话自动命名：
  - 新建/默认会话在首条用户消息发送后自动改名
  - 手动重命名后关闭自动命名，避免覆盖用户自定义标题
- 输入快捷键增强：
  - 支持 `Enter` 发送
  - 支持 `Ctrl+Enter` / `Cmd+Enter` 发送
  - 保留 `Shift+Enter` 换行
- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 操练场归档与排序增强 ✅ (2026-03-06)

- 新增会话归档能力：
  - `归档/恢复` 会话按钮
  - `显示归档` 开关（控制是否展示归档会话）
- 新增会话手动排序：
  - `上移/下移` 按钮
  - 在相同分组（归档状态 + 置顶状态）内调整顺序
- 稳定性改进：
  - 重构并清理 Playground 文件中历史重复函数定义问题
  - 保留已有能力：复制/编辑/重生/删除、导入导出、自动命名、流式输出
- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 操练场会话标签与筛选 ✅ (2026-03-06)

- 新增会话标签：
  - 标签范围：`工作 / 生活 / 测试`
  - 会话标题显示标签前缀
  - 支持快速修改当前会话标签
- 新增标签筛选：
  - `全部标签` + 单标签筛选
  - 与关键词搜索可叠加使用
  - 筛选状态持久化到本地
- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 令牌管理可用性修复 ✅ (2026-03-06)

- 修复点：
  - 令牌列表支持管理端真实 key 拉取（`reveal=true`）
  - 增加行内 `复制` 按钮
  - 增加 `查看完整 Key` 弹窗（含复制）
- 目标结果：
  - 不展示完整 key 也可直接复制
  - 需要时可查看完整 key 再复制

### 会话统计与空会话清理 ✅ (2026-03-06)

- 新增会话统计：
  - 总会话数、活跃会话数、归档会话数、总消息数、最近活跃时间
- 新增一键清理：
  - `清理空会话` 按钮（带确认）
  - 自动保留/切换到有效会话，避免界面悬空

- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 操作反馈提示增强 ✅ (2026-03-06)

- 令牌管理页：
  - 创建成功、复制成功、撤销成功均有可见提示
- 操练场页：
  - 复制、导入/导出、会话更新、清理空会话等关键操作均有成功提示
- 目标：
  - 降低“点击后无反馈”的不确定体验
- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 令牌页逐行复制状态增强 ✅ (2026-03-06)

- 行内复制按钮状态：
  - `复制` → `复制中...` → `已复制`（或 `复制失败`）
- 失败提示增强：
  - 明确提示剪贴板权限/协议限制（建议 HTTPS 或 localhost）
- 质量验证：
  - 前端类型检查通过：`npm run type-check`

### 前端白屏稳定性修复 ✅

- 修复“切换子页面后整站空白”高频问题：
  - `frontend/src/App.vue` 增加全局错误边界，拦截页面级运行时异常，避免整站崩溃
  - `frontend/src/router/index.ts` 增加 `router.onError` 兜底，导航错误自动回退到 `/dashboard`
  - `frontend/src/stores/stats.ts` / `frontend/src/stores/devtools.ts` 增加响应数据归一化，兼容对象/数组混合返回形状

### DevPipeline 崩溃修复 ✅

- 修复报错：`TypeError: store.pipelineEvents is not iterable`
  - 根因：后端 `GET /api/devtools/pipeline/last` 返回 `{events:[...]}`，前端按数组直接迭代
  - 修复：
    - `frontend/src/stores/devtools.ts` 兼容解析 `{events:[...]}` 与 `[]`
    - `frontend/src/pages/DevPipeline.vue` 迭代前做 `Array.isArray` 守卫

### 仪表盘模型与服务状态去 Mock ✅

- `backend/api/dashboard.py` 改造：
  - 模型列表不再硬编码 4 个 Codex：
    - chat2api 模式：返回 chat2api 模型集
    - 非 chat2api：尝试使用活跃账号调用上游 `/v1/models`
    - 失败回退：使用 usage 统计中出现过的模型
  - 服务状态新增真实字段：`openai_base_url`、`chat2api_mode`、`upstream_status`
- `frontend/src/components/ServiceStatus.vue` 已改为渲染后端真实字段，不再写死“轮询/1.0.0”

### 注册模式开关 (browser/http) ✅

- 新增配置项：`registration.mode`
  - `browser`：浏览器自动化注册（当前默认，稳定性优先）
  - `http`：纯 HTTP 注册链路（速度优先，风控拦截概率更高）
- 后端 `RegistrationService` 已按 `mode` 动态组装 8 步流水线：
  - `browser`：`BrowserSignupStep + BrowserVerifyEmailStep`
  - `http`：`SubmitRegistrationStep + VerifyEmailStep`
- 前端配置页已支持切换该模式（注册设置区域）

### 一键启动与自检脚本 ✅

- 新增 `scripts/dev_stack.sh`
  - `up`：启动 chat2api / backend / frontend
  - `down`：停止全部
  - `status`：查看进程与端口状态
  - `check`：执行 `/docs`、`/v1/models`、`/v1/chat/completions` 基础连通性检查

### 待办登记 ✅

- 新增 `docs/TODO.md`，已登记两项 P0 待办：
  - 模型真值测试（声明模型名 vs 实际 req_model 映射）
  - 纯 HTTP 注册流程实测（`registration.mode=http`）

### 本地代理可用性核验（2026-03-06） ✅

- 目标：验证“已注册账号是否真的可对话”且“不是伪造本地直连结果”
- 实测请求：
  - `POST http://127.0.0.1:8001/v1/chat/completions`
  - `Authorization: Bearer <active sk token from tokens.db>`
  - `model=gpt-4o-mini`
  - 返回：`200`，`model=gpt-4o-mini-2024-07-18`，内容 `验证通过`
- 前后证据（数据库增量）：
  - `tokens.total_requests: 17 -> 18`
  - `tokens.total_tokens: 422 -> 440`
  - `usage_logs count: 17 -> 18`
  - 最新 `usage_logs` 记录：`account_id=5`, `model=gpt-4o-mini`, `status_code=200`, `request_tokens=16`, `response_tokens=2`
- 结论：请求确实经由后台账号池落到已注册账号（`account_id=5`），非伪造返回。

### 验证结果

```bash
cd backend && .venv/bin/python -m pytest tests/test_api_dashboard.py tests/test_devtools.py -v
# 8 passed

cd frontend && npm run type-check && npm run build
# pass
```

## 项目概述

codex2api 是一个 AI 模型 API 聚合管理工具，用于统一管理多个 OpenAI/Codex 账号并将其转化为标准 OpenAI 兼容 API 接口。

- **作者**: Zevan
- **技术栈**: FastAPI (Python 3.12) + Vue 3 + Vite + Tailwind CSS
- **状态**: 本地开发阶段，尚未上线

---

## 架构总览

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Vite + Tailwind)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────┐ ┌───────┐  │
│  │Dashboard │ │Accounts  │ │Config│ │Tokens│ │ Logs  │  │
│  └──────────┘ └──────────┘ └──────┘ └──────┘ └───────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────┐                      │
│  │  Stats   │ │  Login   │ │About │                      │
│  └──────────┘ └──────────┘ └──────┘                      │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────────────┐
│  Backend (FastAPI)                                        │
│                                                          │
│  /api/*  管理端 (JWT 鉴权)                                │
│  ├── /api/auth/login, /api/auth/me                       │
│  ├── /api/dashboard/stats, /api/accounts                 │
│  ├── /api/tokens, /api/config                            │
│  ├── /api/logs, /api/stats/*                             │
│  └── /api/pipeline/register, /api/pipeline/status        │
│                                                          │
│  /v1/*   OpenAI 兼容代理 (Bearer sk-xxx 鉴权)            │
│  ├── /v1/models                                          │
│  └── /v1/chat/completions (流式 SSE + 非流式)            │
│                                                          │
│  chat2api 转换层 (已完成 ✅):                              │
│  ├── chat2api v1.8.8-beta2 → localhost:5005              │
│  ├── 安全令牌自动获取 (VM→PoW→Turnstile→Conduit)         │
│  ├── OpenAI API ↔ backend-api 格式转换                   │
│  └── chatgpt.com/backend-api/conversation 调用           │
│                                                          │
│  后台服务:                                                │
│  ├── HealthChecker  (定时探活, 冷却恢复, 封禁)            │
│  └── TokenRefresher (access_token 自动刷新)              │
│                                                          │
│  Pipeline 引擎:                                          │
│  └── 8 步注册流水线 (OAuth2+PKCE)                        │
│                                                          │
│  存储层: SQLite (accounts, tokens, stats, account_health)│
└──────────────────────────────────────────────────────────┘
```

---

## 开发阶段完成情况

### 基础设施 (已完成)

| 模块 | 文件 | 说明 |
|------|------|------|
| Pipeline 框架 | `src/pipeline/base.py, context.py, runner.py` | Step 接口 + 不可变 Context + 顺序执行 + 重试 |
| TalentMail 集成 | `src/integrations/talentmail.py` | 临时邮箱创建、收件箱轮询、验证码提取 |
| 加密存储 | `src/storage/account_store.py` | SQLite + Fernet AES 密码加密 |
| 令牌存储 | `src/storage/token_store.py` | sk-xxx 生成、CRUD、用量追踪 |
| 统计存储 | `src/storage/stats_store.py` | 按小时/日/模型/账号聚合查询 |
| 配置管理 | `src/config/settings.py` | Pydantic Settings + YAML + 环境变量 |
| 日志系统 | `src/utils/logger.py, log_collector.py` | structlog JSON + 内存收集器 |

### P0 - OpenAI 兼容 API 代理 (已完成)

| 模块 | 文件 | 说明 |
|------|------|------|
| 代理路由 | `api/openai_proxy.py` | GET /v1/models, POST /v1/chat/completions |
| 流式支持 | 同上 | SSE StreamingResponse, data: [DONE] |
| 令牌鉴权 | `src/middleware/auth.py` | Bearer sk-xxx 验证, OpenAI 错误格式 |
| 账号池 | `src/services/account_pool.py` | Round-robin 选号 |
| 上游客户端 | `src/integrations/openai_api.py` | OpenAIChatClient (httpx, trust_env=False) |
| 用量记录 | token_store + stats_store | 请求数/Token 数自动累加 |

### P1 - 账号池增强 (已完成)

| 模块 | 文件 | 说明 |
|------|------|------|
| 健康表 | `account_store.py` | account_health 表 (runtime_status, failures, cooldown) |
| 持久化冷却 | `account_pool.py` | 改内存 → DB, 重启不丢失 |
| 健康检查器 | `src/services/health_checker.py` | 后台 asyncio 任务, list_models 探活 |
| 自动恢复 | 同上 | cooling 到期 → active |
| 封禁机制 | 同上 | 连续失败超阈值 → banned |

### P2 - 管理端鉴权 (已完成)

| 模块 | 文件 | 说明 |
|------|------|------|
| JWT 登录 | `api/auth.py` | POST /api/auth/login, GET /api/auth/me |
| Admin 中间件 | `src/middleware/auth.py` | require_admin_token (JWT 校验) |
| 路由保护 | `app.py` | /api/* 统一 Depends, /api/auth/login 除外 |
| 前端登录页 | `frontend/src/pages/Login.vue` | 表单 + 错误提示 + 暗色支持 |
| 路由守卫 | `frontend/src/router/index.ts` | beforeEach 跳转 /login |
| 请求拦截 | `frontend/src/api/client.ts` | 自动附加 JWT header |

### P3 - 会话管理 (已完成)

| 模块 | 文件 | 说明 |
|------|------|------|
| Token 字段 | `account_store.py` | +6 列: refresh_token, token_expires_at, token_status 等 |
| 刷新服务 | `src/services/token_refresher.py` | 后台自动刷新, 退避重试, invalid_grant 放弃 |
| OAuth2 刷新 | `openai_api.py` | refresh_access_token (框架, 参数占位) |
| 协同机制 | `health_checker.py` | 401/403 不算健康失败, 交给 refresher |
| 池过滤 | `account_pool.py` | 排除 expired/refreshing/invalid_grant 账号 |

### P3.5 - usage_limited 自动轮换 (已完成, 2026-03-05)

| 模块 | 文件 | 说明 |
|------|------|------|
| mark_usage_limited | `account_pool.py` | 429 → usage_limited, cooldown 到次日 UTC 0:00 |
| 内联恢复 | `account_pool.py` | acquire_account 检查 cooling + usage_limited 到期恢复 |
| 429 检测 | `openai_proxy.py` | `_is_quota_error()` 识别 429/rate_limit/insufficient_quota |
| 代理联动 | `openai_proxy.py` | list_models + chat_completions 429 → mark_usage_limited |
| 健康检查恢复 | `health_checker.py` | usage_limited 到期自动恢复, 到期前不探活 |
| 测试 | `test_account_health.py` + `test_health_checker.py` | 6 个新用例 |

### P4.5 - chat2api 集成 (已完成, 2026-03-05)

| 模块 | 文件 | 说明 |
|------|------|------|
| chat2api 部署 | `/home/talent/projects/chat2api/` | lanqian528/chat2api v1.8.8-beta2, localhost:5005 |
| 静态模型列表 | `openai_proxy.py` | `_CHAT2API_MODELS` + `_static_models_response()`, chat2api 不支持 /v1/models |
| localhost 检测 | `openai_proxy.py` | `list_models()` 检测 localhost 返回静态列表 |
| 代理跳过 | `openai_proxy.py` | `_build_chat_client()` 检测 localhost 跳过 HTTP 代理 |
| 探针跳过 | `health_checker.py` | 新增 `skip_probe` 参数, chat2api 模式下跳过 list_models 探活 |
| 应用适配 | `app.py` | 检测 chat2api 模式, 传递 `skip_probe=True` 给 HealthChecker |
| 配置变更 | `settings.yaml` | `openai.base_url` → `http://localhost:5005` |
| 测试更新 | `test_openai_proxy.py` | `test_list_models` 改为验证静态模型列表 |

#### chat2api 集成修复记录

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | Fernet 加密密钥不匹配 | 用 test key 保存账号，settings 用不同密钥 | 重新保存账号使用 settings 密钥 |
| 2 | HealthChecker 502 | chat2api 不支持 /v1/models → 账号标记 cooling | `skip_probe=True` 跳过探针 |
| 3 | 代理回退 Bug | `openai_proxy=""` 回退到 `http_proxy=127.0.0.1:7897` | localhost 检测跳过代理 |
| 4 | test_list_models 失败 | 测试期望上游响应但 localhost 返回静态列表 | 测试改为验证静态列表 |

#### 验证结果

```
全链路验证通过:
  客户端 (sk-xxx) → 后端 (8001) → chat2api (5005) → ChatGPT backend-api

  ✅ 非流式: POST /v1/chat/completions → 200 JSON response
  ✅ 流式:   POST /v1/chat/completions?stream=true → SSE text/event-stream
  ✅ 模型列表: GET /v1/models → 静态列表 (12 models)
  ✅ 测试: 49/49 通过

测试账号: tmhgx3r3@talenting.vip (account_id=5, free plan, active)
```

### P4 - 注册自动化 (已完成)

| 模块 | 文件 | 说明 |
|------|------|------|
| 注册客户端 | `openai_api.py` | 7 个方法: init_auth → submit → verify → exchange → profile |
| 8 步流水线 | `src/steps/*.py` | 邮箱创建 → 注册 → 等验证码 → 验证 → 电话(可跳) → 换 token → 资料 → 升级(可跳) |
| 注册服务 | `src/services/registration_service.py` | 组装 Pipeline, 成功自动存账号 |
| API | `api/pipeline_api.py` | POST /api/pipeline/register, GET /api/pipeline/status |
| 可选步骤 | settings | skip_phone_verification, skip_upgrade_plus |

### 前端页面 (已完成)

| 页面 | 文件 | 功能 |
|------|------|------|
| 仪表盘 | `Dashboard.vue` | 6 卡片 + 用量 + 模型 + 服务状态 |
| 账号管理 | `Accounts.vue` | CRUD 表格 + 搜索 + 状态徽章 |
| 配置 | `Config.vue` | 4 分区设置表单 |
| 令牌管理 | `Tokens.vue` | 创建/吊销 + key 展示弹窗 |
| 统计 | `Stats.vue` | CSS 柱状图 + 模型分布 |
| 日志 | `Logs.vue` | 级别/来源/搜索过滤 + 分页 |
| 登录 | `Login.vue` | JWT 登录表单 |
| 关于 | `About.vue` | 作者 + 功能 + 免责 |
| 布局 | `AdminLayout.vue` | 可折叠侧边栏 + 暗色模式 + 独立滚动 |

---

## 测试统计

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| test_pipeline.py | 3 | Context 不可变, Runner 成功/失败 |
| test_talentmail.py | 3 | 登录, 创建邮箱, 等待验证码 |
| test_api_dashboard.py | 2 | 仪表盘统计, 账号 CRUD |
| test_tokens_api.py | 1 | Token CRUD |
| test_config_api.py | 2 | 配置读取(脱敏), 配置更新 |
| test_logs_api.py | 3 | 日志查询, 过滤, 清空 |
| test_openai_proxy.py | 5 | 无鉴权 401, 无效 token 401, models, chat, SSE |
| test_account_health.py | 8 | 健康记录, 失败持久化, cooling 不选, banned, usage_limited CRUD/恢复/midnight |
| test_health_checker.py | 5 | 探活成功, 失败冷却, cooling 恢复, usage_limited 恢复, usage_limited 不探活 |
| test_auth.py | 4 | 登录成功/失败, me 有效/无效 |
| test_token_refresher.py | 4 | 刷新成功, invalid_grant, 未过期跳过, 401 不计失败 |
| test_registration.py | 4 | Pipeline 成功, 跳过电话, 保存账号, API 端点 |
| test_devtools.py | 5 | 日志持久化, 订阅者, Pipeline 事件, 测试 API, 历史日志 |
| **总计** | **49** | — |

---

### DevTools 开发工具模块 (已完成)

| 模块 | 后端 | 前端 | 说明 |
|------|------|------|------|
| 实时日志 | `WS /ws/logs` + 日志归档 | `DevLogs.vue` | WebSocket 推送 + 暂停/过滤 + 按天 JSONL 归档 |
| Pipeline 可视化 | `WS /ws/pipeline` + 事件回调 | `DevPipeline.vue` | 8 步卡片 + 状态图标 + 耗时 + 触发注册 |
| 测试面板 | `WS /ws/test` + subprocess | `DevTest.vue` | 一键 pytest + 终端风格输出 + 汇总 |
| 历史日志 | `GET /api/devtools/logs/*` | DevLogs 历史标签 | 按天滚动 JSONL 文件 + 分页查看 |

---

## 部署架构

```
┌─────────────────────┐     ┌──────────────────────┐
│  本地开发机           │     │  云服务器              │
│                     │     │                      │
│  Frontend (5173)    │     │  TalentMail (邮件服务) │
│  Backend  (8000)    │────▶│  POST /api/pool       │
│                     │     │  GET /api/pool/xx/... │
│  Browser            │     │                      │
└─────────────────────┘     └──────────────────────┘
         │
         │ HTTPS
         ▼
┌─────────────────────────────────┐
│  ChatGPT (注册 + API 调用)       │
│                                 │
│  chatgpt.com                    │
│  ├── /api/auth/* (注册/登录)     │
│  ├── /backend-api/conversation  │ ← chat2api 主调用端点
│  └── /backend-anon/sentinel/*   │ ← 安全令牌获取
│                                 │
│  auth0.openai.com (OAuth 认证)  │
└─────────────────────────────────┘
```

- 后端本地运行，通过网络访问云端 TalentMail 和 OpenAI API
- 前端本地运行，仅与本地后端通信
- TalentMail 的 `base_url` 配置为云服务器地址即可

---

## TalentMail 修复记录

### Fix 1: dual-deliver 传输链路断裂 (2026-03-03) ✅

| 项 | 说明 |
|---|------|
| 问题 | 所有邮箱都收不到邮件，Postfix dual-deliver pipe 有竞态条件 + LMTP 协议错误 |
| 修复 | 去掉 dual-deliver，恢复标准 Dovecot LMTP；mail_sync.py 新增临时邮箱同步 |
| 文件 | `user-patches.sh`, `mail_sync.py`, `main.py` |
| 部署 | 需手动 `cp config/mail/user-patches.sh data/mailserver/config/`（data/ 被 .gitignore） |
| 文档 | `talentmail/docs/troubleshooting/mail-delivery-fix.md` |

### Fix 2: Dovecot SQL UNION temp_mailboxes (2026-03-04) ✅

| 项 | 说明 |
|---|------|
| 问题 | 临时邮箱收不到邮件，Dovecot user_query 只查 users 表，不认识 temp_mailboxes |
| 修复 | `dovecot-sql.conf.ext.template` 的 user_query + iterate_query 加 UNION ALL temp_mailboxes |
| 文件 | `config/mail/dovecot-sql.conf.ext.template` + 生成的 `.conf.ext` |
| 部署 | bind-mount 方式，deploy.sh 自动重新生成，**不需要**手动复制 |
| 验证 | 云端端到端通过：SMTP → Postfix → LMTP → maildir → mail_sync → PostgreSQL |
| 文档 | `talentmail/docs/05-operations/pool-lmtp-fix-deployment.md` |
| 脚本 | `talentmail/scripts/verify_pool_lmtp_fix.sh` + `test_pool_receive.sh` |

---

## 注册流水线进度

| Step | 名称 | 状态 | 说明 |
|------|------|------|------|
| 1 | CreateTempEmailStep | ✅ 通过 | TalentMail 创建临时邮箱正常 |
| 2 | BrowserSignupStep | ✅ 通过 | Patchright 填写 chatgpt.com 注册表单正常 |
| 3 | WaitForVerificationCodeStep | ✅ 通过 | TalentMail 临时邮箱收到 OpenAI 验证邮件，正则提取 6 位验证码 |
| 4 | BrowserVerifyEmailStep | ✅ 通过 | 验证码 + about-you + work-usage + personal-account + 提取 session token |
| 5 | VerifyPhoneStep | ⏸️ 跳过 | skip_phone_verification=true |
| 6 | SetPasswordStep | ⏸️ 跳过 | access_token 已从 browser session 获取，自动跳过 token exchange |
| 7 | SetProfileStep | ⏸️ 跳过 | profile 已在浏览器 onboarding 中设置，自动跳过 |
| 8 | UpgradePlusStep | ⏸️ 跳过 | skip_upgrade_plus=true |

### Step 3-4 验证通过记录 (2026-03-04) ✅

| 项 | 说明 |
|---|------|
| Step 3 | WaitForVerificationCodeStep: TalentMail 临时邮箱成功接收 OpenAI 验证邮件，正则提取 6 位验证码 |
| Step 4 | BrowserVerifyEmailStep: Patchright 自动输入验证码，完成邮箱验证 + PKCE OAuth 获取 token |
| 前提 | TalentMail Dovecot SQL UNION 修复 (Fix 2) 使临时邮箱可收件 |
| 状态 | Step 1-4 全链路验证通过，注册 + 邮箱验证 + token 获取均正常 |

---

## 已知问题

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | DKIM 密钥每次 deploy.sh 重新生成，需重新配 Cloudflare DNS | 低 | 待优化 |
| 2 | SPF 严格模式：非授权 IP 发件被拒（不影响 OpenAI 真实邮件） | 信息 | 正常行为 |
| 3 | mail_sync 无新邮件时不输出日志，排查时容易误判 | 低 | 待优化 |

---

## 文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 注册流程总结 | `docs/REGISTRATION_FLOW.md` | 8 步流水线详解、数据流、Context 字段 |
| 流水线测试指南 | `docs/PIPELINE_TESTING.md` | 分步测试方法、常见失败排查 |
| 项目进度 | `docs/PROJECT_PROGRESS.md` | 本文档 |
| Playwright 设计 | `docs/PLAYWRIGHT_REGISTRATION.md` | Patchright 自动化架构设计 |
| 部署指南 | `docs/DEPLOYMENT_GUIDE.md` | 生产环境部署 |
| 集成指南 | `docs/INTEGRATION_GUIDE.md` | 第三方集成 |
| OpenAI 注册流程 | `docs/openai-registration-flow.md` | OAuth 端点文档 |
| 免费 API 调研 | `docs/PROJECT_PROGRESS.md#免费账号-api-调用方案调研-2026-03-05` | 免费账号 API 方案 |
| 竞品分析 | `docs/COMPETITOR_ANALYSIS.md` | 朋友 codex2api 系统逆向分析 |
| 纯 HTTP 注册调研 | `docs/HTTP_REGISTRATION_RESEARCH.md` | 10 步流程 + Turnstile 解法 + 开源参考 |
| chat2api 架构设计 | `docs/CHAT2API_ARCHITECTURE.md` | backend-api 调用格式 + 安全令牌 + 实现路线图 |

---

## API 调用方案调研 (2026-03-05, 修订版)

### 关键纠正：朋友的系统实际使用 ChatGPT backend-api

> ⚠️ 之前的调研结论有误，已全面修正。详见 `docs/CHAT2API_ARCHITECTURE.md`

#### 之前的错误假设

```
❌ 注册免费账号 → 获取 sk-proj API Key → 调用 api.openai.com
❌ 免费账号有 $5 额度 + 每天 ~70 次免费 API 配额
❌ 不需要 backend-api 转换层
```

#### 实际情况（深度研究确认）

```
✅ 注册免费 ChatGPT 账号 → 获取 session accessToken (JWT)
✅ 用 accessToken 调用 chatgpt.com/backend-api/conversation
✅ 将 backend-api 响应格式转换为 OpenAI API 兼容格式
✅ "每天 ~70 次" 是 ChatGPT 网页版消息限额（5小时滚动窗口）
```

#### 证据

1. **官方 API 免费试用积分已于 2025 年中完全停止发放**
   - 免费账号只能 3 RPM 用 GPT-3.5-turbo
   - sk-proj key 调用 gpt-4o-mini 等全部返回 `insufficient_quota`（已实测确认）
2. **朋友系统名 "codex2api" = 把 ChatGPT Codex 访问转为 API**
   - 使用 session accessToken，不是 sk-proj key
   - 模型 gpt-5.3-codex 通过 backend-api 调用
3. **所有开源同类项目（chat2api/ChatGPT-to-API/codex-lb）均使用 backend-api**
   - 无任何项目用 sk-proj key + 免费账号 + 官方 API 成功运作

### API 调用验证结果 (2026-03-05)

用真实注册账号 `tmhgx3r3@talenting.vip` (free plan) 实测：

| 测试 | 方式 | 结果 | 结论 |
|------|------|------|------|
| 列出模型 | sk-proj Key → api.openai.com/v1/models | ✅ 101 个模型 | 能列但不能调 |
| 调用对话 | sk-proj Key → chat/completions (7 个模型) | ❌ 全部 `insufficient_quota` | **免费积分已停发** |
| 列出模型 | session JWT → api.openai.com/v1/models | ❌ `Missing scopes` | JWT 无 API 权限 |
| backend-api | session JWT → chatgpt.com/backend-api | ❌ 403 Cloudflare | 需安全令牌绕过 |

### 正确架构：chat2api（ChatGPT → OpenAI API 格式转换）

```
注册 chatgpt.com → 获取 session accessToken (JWT)
  → 调用 chatgpt.com/backend-api/conversation
  → 需先获取 5 层安全令牌 (VM → Requirements → PoW → Turnstile → Conduit)
  → 将 backend-api SSE 响应转换为 /v1/chat/completions 格式
  → AccountPool round-robin 多账号轮换
  → 账号消息限额用完 → usage_limited → 5h 窗口后恢复
```

### 实现路线图

| Phase | 目标 | 说明 |
|-------|------|------|
| **Phase 1** | 单账号跑通 | 接入 chat2api/realasfngl 开源库，验证 backend-api 调用 |
| **Phase 2** | 账号池集成 | 扩展 account_store 存 session token，AccountPool 适配 |
| **Phase 3** | 规模化 | 批量注册、纯 HTTP 注册、安全令牌缓存 |

### 待实现

1. ~~自动化 platform.openai.com 获取 API Key~~ ← 废弃，改用 backend-api 方案
2. ~~接入 chat2api 实现安全令牌 + backend-api 调用~~ ✅ (2026-03-05)
3. ~~OpenAI API → backend-api 请求格式转换~~ ✅ (chat2api 内置)
4. ~~backend-api SSE → OpenAI API SSE 响应格式转换~~ ✅ (chat2api 内置)
5. ~~扩展 account_store 存储 session accessToken~~ ✅ (openai_token 字段)
6. ~~单账号完整链路验证~~ ✅ (2026-03-05 全链路通过)
7. 仪表盘增强: 接入真实用量数据 + 成功率 + 趋势图
8. 进程管理: chat2api + 后端服务状态管理
9. 批量注册 + 自动 token 获取

### 详细设计

详见 `docs/CHAT2API_ARCHITECTURE.md`

---

## 待完成事项

### 高优先级（已完成）— chat2api 转换层
- [x] ~~接入 chat2api 开源库，实现 backend-api 安全令牌 + 调用~~ (2026-03-05, chat2api v1.8.8-beta2)
- [x] ~~格式转换层：OpenAI API ↔ backend-api 请求/响应转换~~ (chat2api 内置)
- [x] ~~扩展 account_store 存储 session accessToken~~ (openai_token 字段存 JWT)
- [x] ~~单账号端到端验证~~ (2026-03-05, 流式 + 非流式全部通过)

### 高优先级（当前）
- [ ] 批量注册面板（数量 + 并发 + 进度 + 成功率）

### 高优先级（已完成）
- [x] ~~Step 3 真实测试：OpenAI 验证邮件 → TalentMail 临时邮箱 → 提取验证码~~ (2026-03-04 通过)
- [x] ~~Step 4 真实测试：Patchright 输入验证码 + PKCE OAuth token 获取~~ (2026-03-04 通过)
- [x] ~~注册成功后自动保存账号到数据库~~ (status=registered, 2026-03-05)
- [x] ~~Step 6-7 条件跳过~~ (access_token 从 browser session 直接获取, 2026-03-05)
- [x] ~~完整注册流水线链路打通~~ (Step 1-8 全部通过/跳过, 2026-03-05)
- [x] ~~post-registration onboarding~~ (work-usage + personal-account + skip tour, 2026-03-05)
- [x] ~~usage_limited 状态 + 消息限额耗尽自动换号~~ (2026-03-05)
- [x] ~~配置 TalentMail 云服务器地址到 settings.yaml~~ (已配置 mail.talenting.vip)
- [x] ~~填入真实 OAuth2 参数~~ (client_id 已配置)
- [x] ~~Turnstile token 获取方案~~ (Patchright 浏览器自动化绕过)
- [x] ~~TalentMail 临时邮箱收邮件修复~~ (Dovecot SQL UNION)
- [x] ~~前端对接 Pipeline API~~ (DevTools Pipeline 页面)
- [x] ~~日志持久化~~ (按天 JSONL 归档)
- [x] ~~前端实时日志查看~~ (WebSocket 推送)

### 中优先级（当前进行中）
- [ ] 仪表盘增强（接入真实用量 + 成功率 + TPM + 趋势图）
- [ ] 账号表增强（运行时状态、请求数、Token 过期、错误信息）
- [ ] 进程管理面板（chat2api + 后端服务启停/状态/日志）
- [ ] 注册任务队列 (支持批量并发注册)
- [ ] 纯 HTTP 注册（提升注册速度到 100+/min）
- [ ] 管理员密码 bcrypt 加密 (当前明文)
- [ ] WebSocket 断线自动重连

### 低优先级
- [ ] Alembic 数据库迁移管理
- [ ] Docker 部署配置
- [ ] CI/CD 流水线
- [ ] 前端国际化 (i18n)
- [ ] 生产环境 JWT secret 强化
