# codex2api - 项目进度文档

> 最后更新: 2026-03-04

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
| test_account_health.py | 4 | 健康记录创建, 失败持久化, cooling 不选, banned |
| test_health_checker.py | 3 | 探活成功, 失败冷却, cooling 恢复 |
| test_auth.py | 4 | 登录成功/失败, me 有效/无效 |
| test_token_refresher.py | 4 | 刷新成功, invalid_grant, 未过期跳过, 401 不计失败 |
| test_registration.py | 4 | Pipeline 成功, 跳过电话, 保存账号, API 端点 |
| test_devtools.py | 5 | 日志持久化, 订阅者, Pipeline 事件, 测试 API, 历史日志 |
| **总计** | **43** | — |

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
┌─────────────────────┐
│  OpenAI API          │
│  api.openai.com     │
│  auth0.openai.com   │
└─────────────────────┘
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

---

## 免费账号 API 调用方案调研 (2026-03-05)

### 关键发现：chatgpt.com 与 platform.openai.com 共享账号体系

chatgpt.com 注册的账号 **可以直接登录 platform.openai.com**，无需另外注册。
这意味着注册流水线创建的账号可以直接获取 API Key，走标准 API 通道。

```
chatgpt.com 注册 (已自动化, Patchright)
    ↓ 同一个 email + password
platform.openai.com 登录
    ↓ 免费获得
API Key (sk-xxx) + $5 额度 (3 个月) + 无需绑卡
    ↓
现有 api.openai.com/v1/chat/completions 代理直接可用 ✅
```

### 免费 API Tier 可用模型与限制

| 模型 | TPM | RPM | RPD | 备注 |
|------|-----|-----|-----|------|
| **gpt-4.1** | 10,000 | 3 | 200 | 高性能文本 |
| **gpt-4.1-mini** | 60,000 | 3 | 200 | 高吞吐 |
| **gpt-4o** | 10,000 | 3 | 200 | 多模态 |
| **gpt-4o-mini** | 60,000 | 3 | 200 | 低成本首选 |
| gpt-3.5-turbo | 40,000 | 3 | 200 | 旧模型 |
| whisper-1 | — | 3 | 200 | 语音识别 |
| tts-1 | — | 3 | 200 | 语音合成 |
| DALL-E 3 | — | 3 | 200 | 图像生成 |
| text-embedding-3-* | — | 3 | 200 | 嵌入 |

**$5 额度用 gpt-4o-mini 约可处理 330 万 tokens。**

官方文档称免费 Tier 不支持 GPT-5 系列，但**实测发现 Codex 模型可用**（见竞品分析）。
免费账号每天约 **70 次请求额度**，额度用完状态变为 `usage_limited`。
升级到 Tier 1 只需累计付费 $5，限制大幅提升（如 gpt-4o: 30,000 TPM）。

### 最新 OpenAI API 模型一览 (2026.03)

| 模型家族 | 模型 | 说明 | 免费可用 |
|---------|------|------|---------|
| GPT-5.2 | gpt-5.2, gpt-5.2-mini, gpt-5.2-nano | 最新旗舰 | ❌ 需付费 |
| GPT-5.1 | gpt-5.1-codex, gpt-5.1-codex-max | Codex 优化 | ❌ 需付费 |
| GPT-5 | gpt-5, gpt-5-mini, gpt-5-nano, gpt-5-pro | 上代旗舰 | ❌ 需付费 |
| GPT-4.1 | gpt-4.1, gpt-4.1-mini | 高吞吐 | ✅ 免费 |
| GPT-4o | gpt-4o, gpt-4o-mini | 多模态 | ✅ 免费 |
| O 系列 | o3, o3-pro, o4-mini | 推理模型 | ❌ 需付费 |
| 旧模型 | gpt-3.5-turbo | 经典 | ✅ 免费 |

### 技术方案（修订版）

**无需 backend-api 转换层**，现有架构直接可用：

核心新增步骤：
1. **用注册好的 chatgpt.com 账号登录 `platform.openai.com`**（Patchright 浏览器自动化）
2. **自动创建 API Key**（浏览器自动化或 platform API）
3. **保存 API Key 到 account_store**（替代 OAuth access_token）
4. **现有代理链路直接工作**：Client → /v1/chat/completions → api.openai.com

### ~~旧方案：ChatGPT backend-api（已废弃）~~

~~之前考虑用 `chatgpt.com/backend-api/conversation` + access_token，~~
~~但发现同一账号可直接登录 platform.openai.com 获取 API Key，方案大幅简化。~~

### 风险

- 自动化登录 platform.openai.com 可能有 Cloudflare / reCAPTCHA
- 免费额度 3 个月过期，需定期注册新账号轮换
- 每账号 3 RPM / 200 RPD，需多账号池 round-robin 提升吞吐
- $5 额度用完后 API Key 可能失效

---

## 待完成事项

### 高优先级（当前）
- [x] ~~Step 3 真实测试：OpenAI 验证邮件 → TalentMail 临时邮箱 → 提取验证码~~ (2026-03-04 通过)
- [x] ~~Step 4 真实测试：Patchright 输入验证码 + PKCE OAuth token 获取~~ (2026-03-04 通过)
- [x] ~~注册成功后自动保存账号到数据库~~ (status=registered, 2026-03-05)
- [x] ~~Step 6-7 条件跳过~~ (access_token 从 browser session 直接获取, 2026-03-05)
- [x] ~~完整注册流水线链路打通~~ (Step 1-8 全部通过/跳过, 2026-03-05)
- [x] ~~post-registration onboarding~~ (work-usage + personal-account + skip tour, 2026-03-05)
- [ ] usage_limited 状态 + 70 次/天额度耗尽自动换号
- [ ] 多账号池吞吐优化：70 req/账号/天 × N 账号 round-robin
- [ ] 批量注册面板（数量 + 并发 + 进度 + 成功率）

### 高优先级（联调必需）
- [x] ~~配置 TalentMail 云服务器地址到 settings.yaml~~ (已配置 mail.talenting.vip)
- [x] ~~填入真实 OAuth2 参数~~ (client_id 已配置)
- [x] ~~Turnstile token 获取方案~~ (Patchright 浏览器自动化绕过)
- [x] ~~TalentMail 临时邮箱收邮件修复~~ (Dovecot SQL UNION)
- [x] ~~前端对接 Pipeline API~~ (DevTools Pipeline 页面)
- [x] ~~日志持久化~~ (按天 JSONL 归档)
- [x] ~~前端实时日志查看~~ (WebSocket 推送)

### 中优先级
- [ ] 注册任务队列 (支持批量并发注册)
- [ ] 管理员密码 bcrypt 加密 (当前明文)
- [ ] WebSocket 断线自动重连
- [ ] DKIM 密钥持久化（已存在则跳过生成）

### 低优先级
- [ ] Alembic 数据库迁移管理
- [ ] Docker 部署配置
- [ ] CI/CD 流水线
- [ ] 前端国际化 (i18n)
- [ ] 生产环境 JWT secret 强化
