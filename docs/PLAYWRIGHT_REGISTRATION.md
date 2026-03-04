# OpenAI 自动注册 — Playwright 浏览器自动化方案

> 最后更新: 2026-03-03

## 为什么需要 Playwright

### 问题: Cloudflare 阻止了 API 直连

经测试，OpenAI 认证相关端点全部受 Cloudflare Managed Challenge 保护：

| 端点 | 保护 | 说明 |
|------|------|------|
| `auth.openai.com/authorize` | CF Managed Challenge | OAuth 授权入口 |
| `auth0.openai.com/dbconnections/signup` | CF Managed Challenge | Auth0 注册 API |
| `auth0.openai.com/u/signup` | CF Managed Challenge | Auth0 注册页面 |
| `auth0.openai.com/oauth/token` | **无保护** | Token 交换 (PKCE) |
| `api.openai.com/v1/*` | Bearer Token 校验 | API 代理使用 |

纯 httpx/curl 请求会收到 403 + Cloudflare JS Challenge 页面，无法完成注册。

### 解决方案: Playwright 真实浏览器

Playwright 启动真实 Chromium 浏览器，自动通过 Cloudflare 验证：
- Chromium 浏览器有完整的 JS 引擎、Canvas、WebGL 指纹
- Cloudflare Managed Challenge 对真实浏览器透明通过
- 不需要第三方验证码服务

---

## 已有的 OAuth 参数

从 OpenAI Codex CLI 开源项目中获取的公开参数：

```
client_id:     app_EMoamEEZ73f0CkXaXp7hrann
authorize_url: https://auth.openai.com/authorize
token_url:     https://auth0.openai.com/oauth/token
redirect_uri:  http://localhost:1455/auth/callback
scope:         openid profile email offline_access
flow:          Authorization Code + PKCE (S256)
```

来源: [opencode-openai-codex-auth](https://github.com/numman-ali/opencode-openai-codex-auth/blob/main/lib/auth/auth.ts)

验证: `https://auth.openai.com/.well-known/openid-configuration` 返回:
- `authorization_endpoint`: `https://auth.openai.com/authorize`
- `token_endpoint`: `https://auth0.openai.com/oauth/token`
- `code_challenge_methods_supported`: `["S256", "plain"]`

---

## 架构设计

### 整体流程

```
┌─────────────────────────────────────────────────────────┐
│                  Pipeline Runner (异步)                   │
│                                                         │
│  Step 1: CreateTempEmail                                │
│  ├── TalentMail API → 创建临时邮箱                       │
│  └── 输出: mailbox_id, email                            │
│                                                         │
│  Step 2: BrowserSignup (Playwright)          ◄── 新!    │
│  ├── 启动 Chromium (headless)                           │
│  ├── 访问 auth.openai.com/authorize?screen_hint=signup  │
│  ├── Cloudflare 自动通过 (真实浏览器)                     │
│  ├── 填入 email → Continue                              │
│  ├── 填入 password → Continue                           │
│  ├── 页面跳转到邮箱验证                                   │
│  └── 输出: page 对象 (保持浏览器打开)                     │
│                                                         │
│  Step 3: WaitForVerificationCode                        │
│  ├── TalentMail API → 轮询收件箱                        │
│  └── 输出: verification_code                            │
│                                                         │
│  Step 4: BrowserVerifyEmail (Playwright)     ◄── 新!    │
│  ├── 在验证页面输入 6 位验证码                            │
│  ├── 提交 → 等待注册完成                                 │
│  ├── 页面跳转到 redirect_uri (带 ?code=xxx)             │
│  ├── 截取 authorization_code                            │
│  ├── 关闭浏览器                                          │
│  └── 输出: authorization_code                           │
│                                                         │
│  Step 5: VerifyPhone (跳过)                             │
│  └── skip_phone_verification=true 时直接跳过             │
│                                                         │
│  Step 6: ExchangeToken (httpx)                          │
│  ├── POST auth0.openai.com/oauth/token (无 CF 保护)     │
│  ├── grant_type=authorization_code                      │
│  ├── PKCE: code_verifier                                │
│  └── 输出: access_token, refresh_token, expires_in      │
│                                                         │
│  Step 7: SetProfile (httpx)                             │
│  ├── PATCH api.openai.com/dashboard/user                │
│  └── 输出: account_info                                 │
│                                                         │
│  Step 8: UpgradePlus (跳过)                             │
│  └── skip_upgrade_plus=true 时直接跳过                   │
│                                                         │
│  ✅ 成功 → 保存到 AccountStore                          │
└─────────────────────────────────────────────────────────┘
```

### 与现有架构的关系

| 组件 | 变化 | 说明 |
|------|------|------|
| Pipeline 框架 | 不变 | Step/Context/Runner 完全复用 |
| Step 1 (CreateTempEmail) | 不变 | TalentMail API 正常工作 |
| Step 2 (SubmitRegistration) | **替换** | httpx → Playwright 浏览器注册 |
| Step 3 (WaitForCode) | 不变 | TalentMail 轮询正常工作 |
| Step 4 (VerifyEmail) | **替换** | httpx → Playwright 浏览器验证 |
| Step 5 (VerifyPhone) | 不变 | 保持跳过 |
| Step 6 (SetPassword→ExchangeToken) | **修改** | 改用 PKCE token 交换 |
| Step 7 (SetProfile) | 不变 | httpx 直连 api.openai.com |
| Step 8 (UpgradePlus) | 不变 | 保持跳过 |
| RegistrationService | **更新** | 组装新的步骤序列 |
| DevTools Pipeline 页面 | 不变 | 事件回调兼容 |

---

## 技术细节

### Playwright 浏览器管理

```python
# 单例模式管理浏览器实例
class BrowserManager:
    """管理 Playwright 浏览器生命周期"""

    # 启动参数 (反检测)
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    # headless="new" 使用新版 headless，指纹更接近真实浏览器
    # 支持配置: headless=True/False 用于调试
```

### Step 2: BrowserSignup 详细流程

```
1. 生成 PKCE pair
   ├── code_verifier: 96 字节 URL-safe 随机串
   └── code_challenge: SHA256(verifier) → base64url

2. 构建 authorize URL
   ├── response_type=code
   ├── client_id=app_EMoamEEZ73f0CkXaXp7hrann
   ├── redirect_uri=http://localhost:1455/auth/callback
   ├── scope=openid profile email offline_access
   ├── code_challenge=<sha256_hash>
   ├── code_challenge_method=S256
   ├── state=<random_hex>
   ├── screen_hint=signup           ← 直接跳转注册页
   └── prompt=login

3. Playwright 操作
   ├── page.goto(authorize_url)
   ├── 等待 Cloudflare 通过 (自动, ~3-5秒)
   ├── 等待注册表单出现
   ├── 填入 email → page.fill('input[name="email"]', email)
   ├── 点击 Continue
   ├── 等待密码输入框出现
   ├── 填入 password → page.fill('input[name="password"]', password)
   ├── 点击 Continue / Submit
   └── 等待页面变为验证码输入页面

4. 输出
   ├── code_verifier (保存到 context.metadata)
   ├── state (保存到 context.metadata)
   └── browser_context (保存到 context.metadata, 用于 Step 4)
```

### Step 4: BrowserVerifyEmail 详细流程

```
1. 输入
   ├── verification_code (来自 Step 3, TalentMail)
   └── browser_context (来自 Step 2)

2. Playwright 操作
   ├── 在验证码输入框中填入 6 位数字
   │   ├── 可能是 6 个独立 <input> (每个一位)
   │   └── 也可能是 1 个 <input> (完整验证码)
   ├── 自动提交 (填满 6 位后自动提交，或点击 Continue)
   └── 等待页面跳转

3. 截取 authorization_code
   ├── 监听 redirect_uri 跳转
   ├── URL: http://localhost:1455/auth/callback?code=xxx&state=yyy
   ├── 提取 code 参数
   └── 验证 state 参数匹配

4. 清理
   ├── 关闭 browser context
   └── 输出: authorization_code
```

### Step 6: ExchangeToken 详细流程

```
1. 输入
   ├── authorization_code (来自 Step 4)
   └── code_verifier (来自 Step 2, 存在 metadata)

2. HTTP 请求 (httpx, 无需浏览器, 无 CF 保护)
   POST https://auth0.openai.com/oauth/token
   Content-Type: application/x-www-form-urlencoded
   Body:
     grant_type=authorization_code
     client_id=app_EMoamEEZ73f0CkXaXp7hrann
     code=<authorization_code>
     code_verifier=<code_verifier>
     redirect_uri=http://localhost:1455/auth/callback

3. 响应
   {
     "access_token": "eyJ...",
     "refresh_token": "xxx...",
     "expires_in": 3600,
     "token_type": "Bearer"
   }

4. 输出
   ├── access_token
   ├── refresh_token
   └── expires_in
```

---

## PKCE (Proof Key for Code Exchange) 说明

```
注册前:
  1. 生成 code_verifier (96 字节随机字符串)
  2. 计算 code_challenge = BASE64URL(SHA256(code_verifier))
  3. 将 code_challenge 附在 authorize URL 中

Token 交换时:
  4. 将 code_verifier 发送到 token endpoint
  5. 服务端验证 SHA256(code_verifier) == 之前收到的 code_challenge
  6. 验证通过，返回 tokens

安全性: 即使 authorization_code 被截取，没有 code_verifier 无法换取 token
```

---

## 文件结构

```
backend/
├── src/
│   ├── integrations/
│   │   ├── openai_api.py          # 保留: Token 交换 + Chat Client
│   │   ├── talentmail.py          # 保留: 邮箱创建 + 验证码
│   │   └── browser.py             # 新增: Playwright 浏览器管理
│   ├── steps/
│   │   ├── email.py               # 保留: CreateTempEmail + WaitForCode
│   │   ├── browser_signup.py      # 新增: BrowserSignupStep
│   │   ├── browser_verify.py      # 新增: BrowserVerifyEmailStep
│   │   ├── token_exchange.py      # 新增: ExchangeTokenStep (PKCE)
│   │   ├── profile.py             # 保留: SetProfile
│   │   ├── verify.py              # 保留: VerifyPhone (skip)
│   │   └── upgrade.py             # 保留: UpgradePlus (skip)
│   ├── services/
│   │   └── registration_service.py  # 更新: 使用新步骤
│   └── pipeline/                    # 不变
│       ├── base.py
│       ├── context.py
│       └── runner.py
├── config/
│   └── settings.yaml              # 更新: authorize_url + client_id
└── pyproject.toml                 # 更新: 添加 playwright 依赖
```

---

## 反检测与稳定性

### Playwright 配置

```python
browser = playwright.chromium.launch(
    headless=True,               # 无头模式 (生产)
    args=[
        "--disable-blink-features=AutomationControlled",
    ],
)

context = browser.new_context(
    viewport={"width": 1280, "height": 720},
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    locale="en-US",
    timezone_id="America/New_York",
)

# 移除 navigator.webdriver 标记
page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
```

### 等待策略

- **Cloudflare 通过**: 等待特定元素出现 (注册表单)，超时 30 秒
- **表单操作**: 每个操作间添加随机延迟 (0.5-2 秒)，模拟真人
- **页面跳转**: 等待 redirect_uri 的 URL 出现，超时 60 秒
- **验证码输入**: 逐个字符输入，间隔 100-300ms

### 错误处理

| 场景 | 处理方式 |
|------|---------|
| CF Challenge 超时 | 重试 (最多 2 次) |
| 表单元素找不到 | 截图保存 → 返回错误 |
| 邮箱已注册 | 返回 "email_exists" 错误 |
| 验证码过期 | 重新请求验证码 |
| redirect 拦截失败 | 尝试从 page URL 解析 code |
| 浏览器崩溃 | 确保资源清理 (async with) |

---

## 配置项

### settings.yaml 新增

```yaml
registration:
  headless: true               # false 时显示浏览器窗口 (调试用)
  browser_timeout: 30          # Cloudflare 等待超时 (秒)
  typing_delay_ms: 150         # 模拟打字间隔 (毫秒)
  navigation_timeout: 60       # 页面跳转等待超时 (秒)
```

---

## 凭证汇总

### 管理面板

| 项目 | 值 |
|------|-----|
| 用户名 | `admin-zevan` |
| 密码 | `adminpassword-zevan` |
| 地址 | `http://localhost:5173` (前端) |
| 后端 | `http://localhost:8001` (当前端口) |

### TalentMail

| 项目 | 值 |
|------|-----|
| API 地址 | `https://mail.talenting.vip/api` |
| 登录邮箱 | `test-register@talenting.vip` |
| 密码 | `123456` |

### OpenAI OAuth

| 项目 | 值 |
|------|-----|
| Client ID | `app_EMoamEEZ73f0CkXaXp7hrann` |
| Authorize URL | `https://auth.openai.com/authorize` |
| Token URL | `https://auth0.openai.com/oauth/token` |
| Redirect URI | `http://localhost:1455/auth/callback` |
| Scope | `openid profile email offline_access` |
| Flow | Authorization Code + PKCE (S256) |

### 云服务器

| 项目 | 值 |
|------|-----|
| IP | `111.91.23.109` |
| 地区 | 新加坡 (可直连 OpenAI) |
| TalentMail 域名 | `mail.talenting.vip` |
| 邮箱域名 | `@talenting.vip` |

---

## 依赖安装

```bash
cd backend

# 安装 playwright Python 包
.venv/bin/pip install playwright

# 下载 Chromium 浏览器 (约 150MB)
.venv/bin/playwright install chromium

# 安装系统依赖 (Linux)
.venv/bin/playwright install-deps chromium
```
