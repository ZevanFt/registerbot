# chat2api 架构分析与系统设计

> 2026-03-05 基于深度研究重写

---

## 1. 关键纠正：朋友的系统如何工作

### 之前的错误理解

```
❌ 注册免费账号 → 获取 sk-proj API Key → 调用 api.openai.com/v1/chat/completions
❌ 免费账号有 $5 额度 + 每天 ~70 次免费请求配额
❌ 不需要 backend-api 转换层
```

### 实际情况

```
✅ 注册免费 ChatGPT 账号 → 获取 session accessToken (JWT)
✅ 用 accessToken 调用 chatgpt.com/backend-api/conversation
✅ 将 backend-api 的响应格式转换为 OpenAI API 兼容格式
✅ "每天 ~70 次" 是 ChatGPT 网页版消息限额，不是官方 API 配额
```

### 证据

1. **官方 API 免费试用积分已于 2025 年中完全停止发放**
   - 免费账号只能 3 RPM 用 GPT-3.5-turbo，无法使用 GPT-4/Codex 系列
   - 这就是为什么 sk-proj key 测试 101 个模型全部返回 `insufficient_quota`

2. **朋友的系统名叫 "codex2api"**
   - 字面意思：把 Codex (ChatGPT 网页版) 访问权转换为 API 格式
   - 模型名 gpt-5.3-codex 是 ChatGPT 内部模型，通过 backend-api 调用

3. **注册流程最后一步是 "回调 chatgpt.com → 拿 access_token"**
   - 拿的是 ChatGPT session token，不是 API Key
   - 我们的 browser_verify.py 已经实现了这一步（从 /api/auth/session 提取）

4. **开源项目验证**
   - chat2api、ChatGPT-to-API、realasfngl/ChatGPT — 全部调用 backend-api
   - codex-openai-proxy、CLIProxyAPI — 也是 ChatGPT OAuth → Responses API
   - **没有任何项目用 sk-proj key + 免费账号 + 官方 API 成功运作**

---

## 2. ChatGPT backend-api 调用格式

### 端点

```
POST https://chatgpt.com/backend-api/conversation
```

### 请求头（必须全部提供）

```
Authorization: Bearer <accessToken>           # ChatGPT session JWT
Content-Type: application/json
openai-sentinel-chat-requirements-token: ...  # 安全令牌 1
openai-sentinel-proof-token: ...              # 安全令牌 2 (PoW)
openai-sentinel-turnstile-token: ...          # 安全令牌 3
x-conduit-token: ...                          # 安全令牌 4
oai-device-id: <uuid>                         # 设备 ID
oai-echo-logs: <timing_data>                  # 时序数据
```

### 请求体

```json
{
  "action": "next",
  "messages": [
    {
      "id": "uuid-here",
      "author": { "role": "user" },
      "content": {
        "content_type": "text",
        "parts": ["你好，帮我写一个排序算法"]
      },
      "metadata": {}
    }
  ],
  "model": "gpt-5.3-codex",
  "parent_message_id": "uuid-here",
  "conversation_id": null,
  "history_and_training_disabled": true,
  "timezone_offset_min": -480
}
```

### 响应（SSE 流）

```
data: {"message":{"id":"xxx","author":{"role":"assistant"},"content":{"content_type":"text","parts":["你好"]},"status":"in_progress"},...}
data: {"message":{"id":"xxx","author":{"role":"assistant"},"content":{"content_type":"text","parts":["你好！这是"]},"status":"in_progress"},...}
...
data: [DONE]
```

---

## 3. 五层安全令牌 Pipeline

调用 backend-api 之前必须获取 5 个安全令牌：

### 3.1 VM Token（本地生成）
- 编码 18 元素配置数组（magic constants、时间戳、User-Agent、构建版本等）为 Base64
- 纯客户端计算，不需要网络请求

### 3.2 Requirements Token（服务器获取）
- `POST /backend-anon/sentinel/chat-requirements` + `{"p": vm_token}`
- 返回：requirements_token + PoW 挑战参数 + Turnstile 字节码

### 3.3 Proof-of-Work Token（本地计算）
- FNV-1a 哈希算法暴力破解
- 最多 500,000 次迭代，通常 1-5 秒完成
- 难度由服务器动态调整

### 3.4 Turnstile Token（最复杂）
- XOR 解密混淆字节码
- AST 分析提取密钥
- 构建浏览器指纹载荷
- 多层 XOR 加密

### 3.5 Conduit Token
- `POST /f/conversation/prepare` + 时区信息
- 每个会话一次

### 总耗时：3-8 秒/对话周期

---

## 4. 正确的系统架构

### 4.1 整体流程

```
┌───────────────────────────────────────────────────────────────────┐
│                     codex2api 系统架构                              │
│                                                                   │
│  ┌────────────┐    ┌──────────────┐    ┌────────────────────────┐ │
│  │ 注册模块    │    │ 账号池管理    │    │ API 代理 (chat2api)    │ │
│  │            │    │              │    │                        │ │
│  │ Patchright │───▶│ account_store│───▶│ /v1/chat/completions   │ │
│  │ or HTTP    │    │ (email,pwd,  │    │ /v1/models             │ │
│  │ 注册       │    │  token,      │    │                        │ │
│  │            │    │  cookies)    │    │ ┌──────────────────┐   │ │
│  └────────────┘    │              │    │ │ 格式转换层       │   │ │
│                    │ round-robin  │    │ │                  │   │ │
│                    │ + cooldown   │    │ │ OpenAI API 格式  │   │ │
│                    │ + recovery   │    │ │       ↕          │   │ │
│                    └──────────────┘    │ │ backend-api 格式 │   │ │
│                                       │ └──────────────────┘   │ │
│                                       │                        │ │
│                                       │ ┌──────────────────┐   │ │
│                                       │ │ 安全令牌 Pipeline │   │ │
│                                       │ │ VM → Req → PoW   │   │ │
│                                       │ │ → Turnstile      │   │ │
│                                       │ │ → Conduit        │   │ │
│                                       │ └──────────────────┘   │ │
│                                       └────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│                    chatgpt.com/backend-api/conversation            │
└───────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流

```
Client 请求:
POST /v1/chat/completions
{ "model": "gpt-5.3-codex", "messages": [...] }

  ↓ 1. Token 鉴权 (sk-xxx)
  ↓ 2. AccountPool 选号 (round-robin)
  ↓ 3. 获取安全令牌 (5-token pipeline, 3-8s)
  ↓ 4. 格式转换: OpenAI → backend-api

POST chatgpt.com/backend-api/conversation
Authorization: Bearer <session_access_token>
+ 5个安全令牌头

  ↓ 5. SSE 响应
  ↓ 6. 格式转换: backend-api → OpenAI

返回 Client:
{ "choices": [{"message": {"role": "assistant", "content": "..."}}] }
```

### 4.3 账号生命周期（修正版）

```
注册 → active → rate_limited (消息限额到) → active (窗口恢复)
                ↘ cooling (token 过期) → 重新登录 → active
                ↘ banned (IP/行为检测)
                ↘ abandoned (多次恢复失败)
```

注意：ChatGPT 的消息限额是 **5 小时滚动窗口**，不是 UTC 0:00 重置。
- 高级模型 (GPT-5.3): ~10 消息/5小时
- 基础模型 (GPT-4o-mini): 更高限额
- 朋友观测到的 ~70 次/天 是多模型混合使用的总计

---

## 5. 实现路线图

### Phase 1：基础可用（使用现有开源库）

**目标**：先跑通 1 个账号的 backend-api 调用

| 步骤 | 说明 | 复杂度 |
|------|------|--------|
| 1.1 | 接入 chat2api 或 realasfngl/ChatGPT 作为后端 | 中 |
| 1.2 | 用现有注册的 accessToken 测试 backend-api 调用 | 低 |
| 1.3 | 确认安全令牌 pipeline 正常工作 | 高 |
| 1.4 | 实现 OpenAI → backend-api 格式转换 | 中 |
| 1.5 | SSE 流式响应转换 | 中 |

### Phase 2：账号池集成

| 步骤 | 说明 | 复杂度 |
|------|------|--------|
| 2.1 | 扩展 account_store 存储 session token + cookies | 低 |
| 2.2 | AccountPool 适配 backend-api 方式 | 中 |
| 2.3 | Token 自动刷新（session 过期 → 重新登录） | 中 |
| 2.4 | Rate limit 检测与自动换号 | 低（已有 usage_limited） |

### Phase 3：规模化

| 步骤 | 说明 | 复杂度 |
|------|------|--------|
| 3.1 | 批量注册 + accessToken 自动获取 | 高 |
| 3.2 | 纯 HTTP 注册（提升注册速度） | 高 |
| 3.3 | 安全令牌缓存（减少每次调用的开销） | 中 |
| 3.4 | 多账号并发调用 | 中 |

---

## 6. 现有代码可复用部分

| 现有模块 | 可复用 | 需改造 |
|---------|--------|--------|
| 注册流水线 (steps/*) | ✅ 完全复用 | — |
| account_store | ✅ 存储结构 | 需增加 session_token + cookies 字段 |
| AccountPool | ✅ round-robin + cooldown | 需适配消息限额检测 |
| HealthChecker | ✅ 探活逻辑 | 需改用 backend-api 探活 |
| token_store | ✅ sk-xxx 分发 | — |
| stats_store | ✅ 用量统计 | — |
| openai_proxy.py | ❌ 需重写 | 现在直接转发 api.openai.com，需改为调用 backend-api |
| OpenAIChatClient | ❌ 需新增 | 需新增 ChatGPT backend-api 客户端 |
| — | — | 需新增：安全令牌 Pipeline |
| — | — | 需新增：格式转换层 |
| — | — | 需新增：Session 登录/刷新 |

---

## 7. 开源参考项目

| 项目 | 语言 | 说明 | 参考价值 |
|------|------|------|---------|
| [chat2api](https://github.com/lanqian528/chat2api) | Python | 最成熟的 chat2api 实现 | ⭐⭐⭐⭐⭐ 格式转换 + 安全令牌 |
| [realasfngl/ChatGPT](https://github.com/realasfngl/ChatGPT) | Python | 完整的安全令牌绕过 | ⭐⭐⭐⭐⭐ 令牌生成算法 |
| [openai-sentinel](https://github.com/leetanshaj/openai-sentinel) | Python | PoW + Sentinel 教学实现 | ⭐⭐⭐⭐ 算法参考 |
| [codex-lb](https://github.com/Soju06/codex-lb) | - | 多账号负载均衡 + Dashboard | ⭐⭐⭐ 架构参考 |
| [codex-openai-proxy](https://github.com/Securiteru/codex-openai-proxy) | Rust | Responses API 格式转换 | ⭐⭐⭐ 格式参考 |

---

## 8. 风险与应对

| 风险 | 应对 |
|------|------|
| ChatGPT 安全令牌算法频繁更新 | 依赖活跃维护的开源库，定期跟进 |
| Cloudflare 拦截 backend-api 请求 | 使用正确的 TLS 指纹 + cookies |
| 账号被批量封禁 | 注册时使用代理、随机化行为、控制频率 |
| 消息限额降低 | 更多账号轮换、优先低消耗模型 |
| OpenAI 关闭免费 ChatGPT | 核心风险，需持续关注政策变化 |
