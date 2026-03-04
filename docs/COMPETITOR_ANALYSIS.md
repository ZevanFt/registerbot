# 竞品分析：朋友的 codex2api 系统

> 基于 6 张截图逆向推演，2026-03-05

---

## 1. 系统概览

朋友的 codex2api 是一个已跑通的大规模 OpenAI 免费账号注册 + API 代理系统：
- 总账号 **1173**，活跃 **757**，已废弃 **416**（~35% 损耗率）
- 日处理 **3.3K 请求**，**142.8M tokens**
- 主力模型：**gpt-5.3-codex**（最新 Codex 模型）
- 注册速度：100 个账号 / 2 分钟 / 50 并发

---

## 2. 注册流程对比

### 朋友的方案：纯 HTTP + Capsolver（10 步）

```
1. GET chatgpt.com → 拿 CSRF + cookies
2. POST /api/auth/signin/login-web → 拿 authorize URL
3. GET auth.openai.com/authorize?...&prompt=signup → 拿注册页面 state
4. POST 邮箱到 auth.openai.com 内部 API
5. POST 密码
6. 解 Turnstile (Capsolver)
7. 等验证码 (RokMail)
8. POST 验证码
9. POST name + age
10. 回调 chatgpt.com → 拿 access_token
```

- 100 个账号 2 分 5 秒，并发 50
- 纯 HTTP 请求，无浏览器开销
- Turnstile 用 Capsolver 付费服务解决
- 验证码用 RokMail（类似我们的 TalentMail）
- 注册后还需：填生日 → work usage → personal account → 跳过 onboarding

### 我们的方案：Patchright 浏览器自动化（8 步）

- 单个账号需要几分钟
- 真实浏览器绕过 Cloudflare，无需 Capsolver
- 并发受浏览器资源限制
- 优势：不依赖第三方付费服务

### 差距

| 维度 | 朋友 | 我们 |
|------|------|------|
| 注册速度 | 100 个/2 分钟 | 1 个/几分钟 |
| 并发能力 | 50+ | 1（受浏览器限制）|
| Turnstile | Capsolver（付费） | Patchright（免费）|
| 邮件服务 | RokMail | TalentMail（自建）|
| 注册后处理 | 填生日 + onboarding | 尚未实现 |

---

## 3. 模型使用情况

### 免费账号可用的 Codex 模型（实际验证）

| 模型 | 请求数 | 输入 tokens | 输出 tokens | 均延迟 |
|------|--------|------------|------------|--------|
| **gpt-5.3-codex** | 3.2K | 141.8M | 998.0K | 12.3Kms |
| gpt-5-codex-mini | 61 | 2.6K | 2.1K | 2.6Kms |
| gpt-5.2-codex | 3 | 0 | 0 | 17.6Kms |
| gpt-5.1-codex-max | 18 | 386 | 2.8K | 4.8Kms |
| gpt-5.1-codex | 15 | 238 | 292 | 2.4Kms |
| gpt-5-codex | 15 | 260 | 260 | 1.9Kms |

**关键发现**：免费账号不仅能用 gpt-4o-mini，还能用最新的 Codex 系列模型！
之前的调研说免费 Tier 不支持 GPT-5 系列，但实际上 Codex 模型似乎走的是不同的访问路径。

### 免费额度

- 免费账号每天约 **70 次请求额度**（截图实证：请求数=70 后变为 usage_limited）
- 账号用完额度后状态变为 `usage_limited`（截图显示："额度已用尽"）
- 需要大量账号轮换来维持吞吐（朋友用 757 个活跃账号）

---

## 4. 前端功能对比

### 朋友有，我们缺少的功能

#### 4.1 批量注册面板

朋友的注册面板：
- 数量输入（如 100）
- 并发选择（如 50）
- 代理开关
- 自动上传开关（注册完自动导入账号池）
- 实时进度条 + 耗时显示
- 成功 / 失败 / 不确定 计数器
- **每步成功率监控**（邮箱创建 100/100, OAuth 初始化 100/100, ...）
- **总成功率**显示

我们的 DevPipeline：
- 仅支持单次触发
- 无数量/并发控制
- 无进度条
- 无成功率统计

#### 4.2 仪表盘增强

朋友多出的指标：
- **当前 TPM**（Tokens Per Minute）— 我们只有 RPM
- **成功率百分比**（93.06%, 97.82%）— 我们没有
- **紧凑状态栏**：总账号 / 活跃 / 冷却 / 封禁 / 过期 / 废弃 一行显示
- **数据分析标签页**：Token 趋势 / 请求趋势 / 模型排行 / 账号排行（集成在仪表盘内）

我们的 Dashboard：
- 有 6 张状态卡片（总账号/活跃/冷却/封禁/过期/废弃）
- 有 3 张用量卡片（请求/Token/RPM）
- 模型列表和服务状态
- 无 TPM、无成功率、无趋势图

#### 4.3 模型排行表

朋友的表：模型 / 请求数 / 输入 tokens / 输出 tokens / 均延迟 / 占比条

我们的 Stats 页：有模型分布但更简单（只有百分比条）

#### 4.4 账号详情增强

朋友显示的字段：
- 邮箱（脱敏）/ 状态 / 请求数 / Token 过期时间 / 连续错误 / 最近错误原因
- `usage_limited` 状态（额度用尽）

我们的 Accounts 页：
- ID / 邮箱 / 套餐 / 状态 / 创建时间 / 操作
- 缺少：请求数、Token 过期、错误信息、usage_limited 状态

### 我们有，朋友截图没看到的功能

- Playground（AI 对话测试）
- DevLogs（实时 WebSocket 日志）
- DevTest（测试面板）
- Config（完整配置管理）
- Token 管理（sk-xxx 分发）

---

## 5. 账号生命周期对比

### 朋友的账号状态

```
注册 → active → usage_limited (额度用尽) → abandoned (废弃)
                ↘ cooling (冷却) → active (恢复)
                ↘ banned (封禁)
                ↘ expired (过期)
```

### 我们的账号状态

```
注册 → registered → active → cooling → active
                           ↘ banned
                           ↘ expired
                           ↘ pending
                           ↘ abandoned
```

**缺少**：`usage_limited` 状态（最关键的免费账号状态）

---

## 6. 技术栈推测（朋友的项目）

- 前端：与我们类似的 Vue + Tailwind 风格
- 注册服务：纯 HTTP (可能 Node.js，截图显示 `lib/register.mjs`)
- Captcha：Capsolver（付费 Turnstile 解决服务）
- 邮件：RokMail
- 域名：204023.xyz（邮箱域名）
- API 代理：与我们类似的 round-robin 账号池

---

## 7. 下一步行动建议

### 短期（利用现有架构）
1. 新增 `usage_limited` 账号状态
2. 仪表盘增加 TPM + 成功率指标
3. 模型排行表增加输入/输出/延迟列
4. 账号表增加请求数、Token 过期、错误信息列
5. 注册后补全流程：填生日 → work usage → personal account → onboarding

### 中期（提升注册效率）
1. 批量注册面板：数量 + 并发 + 进度 + 成功率
2. 评估 Capsolver 接入（纯 HTTP 方案）
3. 注册后自动登录 platform.openai.com 获取 API Key

### 长期（规模化）
1. 账号轮换策略（usage_limited → 换号）
2. 注册任务队列 + 定时补充新账号
3. 多邮件域名支持
