# OpenAI 账户注册流程总结

**更新日期**：2026-03-04
**验证状态**：本地 Step 1-2 已验证，Step 3 依赖 TalentMail 临时邮箱修复（已完成）

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                   Register-Bot Backend                   │
│                                                          │
│  POST /api/pipeline/register                            │
│       ↓                                                  │
│  RegistrationService.register_account()                  │
│       ↓                                                  │
│  PipelineRunner.run(8 steps)                            │
│       ↓                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ TalentMail│  │ Patchright│  │ OpenAI   │              │
│  │ (邮箱)    │  │ (浏览器)  │  │ (API)    │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│       ↓                                                  │
│  AccountStore.save_account() → accounts.db              │
└─────────────────────────────────────────────────────────┘
```

---

## 8 步注册流水线

### Step 1：CreateTempEmailStep（创建临时邮箱）

**文件**：`backend/src/steps/email.py`
**集成**：TalentMail Pool API

```
输入：无（使用 settings.talentmail 配置）
操作：TalentMailClient.create_temp_email(prefix=随机, purpose="openai_registration")
输出：
  - mailbox_id: str     → 用于后续轮询收件箱
  - email: str          → 如 "abc123@talenting.vip"
```

**TalentMail 调用链**：
```
register-bot → POST /api/pool/ → TalentMail Backend
  → PostgreSQL: INSERT INTO temp_mailboxes
  → Docker exec: setup email add (Postfix vmailbox + maildir)
  → 返回 {id, email}
```

---

### Step 2：BrowserSignupStep（浏览器注册）

**文件**：`backend/src/steps/browser_signup.py`（491 行）
**集成**：Patchright（反检测 Playwright 分支）

```
输入：
  - email: str          → Step 1 创建的临时邮箱
  - password: str       → settings.openai.default_password 或用户指定
操作：Patchright 浏览器自动化
输出：
  - browser_session_id  → 存入 metadata
  - _browser_manager    → 存入 metadata
  - _active_page        → 存入 metadata
```

**浏览器自动化流程**：

```
1. 启动 Patchright Chromium（headed 模式，Cloudflare 要求）
2. 导航 → https://chat.openai.com
3. 等待页面加载 + Cloudflare Managed Challenge 自动通过
4. 点击 "Sign up" 按钮
5. 等待注册模态框出现
6. 填写 email → 点击 "Continue"
7. 等待密码输入框出现
8. 填写 password → 点击 "Continue"
9. 等待「Check your inbox」验证邮件页面
10. 返回（浏览器 session 保持活跃，传递给 Step 4）
```

**Cloudflare 绕过关键**：
- Patchright 自动过滤 `navigator.webdriver` 标志
- 使用 headed 模式（headless 被 Cloudflare 拦截）
- 云端用 Xvfb 虚拟显示 (`DISPLAY=:99`)
- 真实浏览器指纹（viewport 1280x720, en-US locale）

**错误处理**：
- `email_exists`：检测页面中 "already" / "exist" 关键词
- `operation_timed_out`：自动点击 "Try again"，最多重试 3 次
- Turnstile CAPTCHA：等待 15 秒自动解决

---

### Step 3：WaitForVerificationCodeStep（等待验证码）

**文件**：`backend/src/steps/email.py`
**集成**：TalentMail Pool API

```
输入：
  - mailbox_id: str     → Step 1 返回的邮箱 ID
操作：TalentMailClient.wait_for_code(mailbox_id, timeout=300, poll_interval=5)
输出：
  - verification_code: str  → 6 位数字验证码
```

**邮件投递链路**（TalentMail 侧）：

```
OpenAI SMTP → 公网 MX 记录 → maillink.talenting.vip:25
  → Postfix → amavis（垃圾邮件检查）→ Dovecot LMTP
  → Dovecot 查询 dovecot-sql.conf.ext:
      SELECT ... FROM users WHERE email = '%u'
      UNION ALL
      SELECT ... FROM temp_mailboxes WHERE email = '%u' AND is_active = true
  → maildir 存储（/var/mail/talenting.vip/<用户名>/）
  → mail_sync.py（每 30 秒 IMAP 轮询）→ PostgreSQL
  → Pool API（/api/pool/{id}/emails）→ register-bot
```

**验证码提取**：
- 正则：`\b(\d{6})\b`
- 搜索顺序：subject → text → body → html

**超时机制**：
- 默认 300 秒（5 分钟）
- 每 5 秒轮询一次 TalentMail API
- 超时抛出 `TimeoutError`

---

### Step 4：BrowserVerifyEmailStep（浏览器验证 + PKCE OAuth）

**文件**：`backend/src/steps/browser_verify.py`（269 行）
**集成**：Patchright + OpenAI OAuth

```
输入：
  - verification_code: str    → Step 3 返回的 6 位验证码
  - 浏览器 session            → Step 2 传递的 metadata
操作：输入验证码 → PKCE OAuth 授权
输出：
  - authorization_code: str   → 存入 metadata
  - code_verifier: str        → 存入 metadata
  - oauth_state: str          → 存入 metadata
```

**分两阶段**：

**阶段 A：输入验证码**
```
1. 在验证码输入框中填入 6 位数字
   - 尝试方式 1：单个输入框直接填入
   - 尝试方式 2：6 个独立输入框逐个填入
   - 尝试方式 3：fallback（键盘输入）
2. 提交 → 等待页面跳转
```

**阶段 B：PKCE OAuth 授权**
```
1. 生成新的 PKCE pair:
   - code_verifier = 96 字节 URL-safe base64
   - code_challenge = SHA256(code_verifier) → base64url
2. 构造 authorize URL:
   GET https://auth.openai.com/authorize
     ?client_id=app_EMoamEEZ73f0CkXaXp7hrann
     &redirect_uri=http://localhost:1455/auth/callback
     &response_type=code
     &scope=openid email profile
     &code_challenge=<code_challenge>
     &code_challenge_method=S256
     &state=<random>
     &nonce=<random>
3. 浏览器导航到 authorize URL
   （已有认证 session → 自动重定向到 redirect_uri?code=xxx&state=yyy）
4. 从 URL 中提取 authorization_code
5. 关闭浏览器 session
```

---

### Step 5：VerifyPhoneStep（手机验证 — 跳过）

**文件**：`backend/src/steps/verify.py`

```
输入：无
操作：检查 settings.registration.skip_phone_verification
输出：skip_reason="Phone verification skipped by configuration"
```

当前配置默认跳过手机验证。

---

### Step 6：SetPasswordStep（Token 交换）

**文件**：`backend/src/steps/password.py`
**集成**：OpenAI OAuth Token Endpoint

```
输入：
  - authorization_code   → Step 4 metadata
  - code_verifier        → Step 4 metadata
操作：HTTP POST token exchange
输出：
  - access_token: str
  - refresh_token: str
  - expires_in: int
```

**Token Exchange 请求**：

```http
POST https://auth0.openai.com/oauth/token
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "code": "<authorization_code>",
  "code_verifier": "<code_verifier>",
  "redirect_uri": "http://localhost:1455/auth/callback",
  "client_id": "app_EMoamEEZ73f0CkXaXp7hrann"
}
```

**注意**：
- `authorization_code` 有效期很短（通常几分钟），Step 4 → Step 6 必须连续执行
- Token URL 使用 `auth0.openai.com`（不是 `auth.openai.com`）
- `trust_env=False` 避免本地 SOCKS 代理干扰

---

### Step 7：SetProfileStep（设置个人资料）

**文件**：`backend/src/steps/profile.py`
**集成**：OpenAI Dashboard API

```
输入：
  - access_token: str   → Step 6 返回
操作：设置用户名 + 创建 onboarding session
输出：
  - account_info: dict  → 包含 profile 和 session 数据
```

**API 调用**：

```http
# 1. 设置用户名
PATCH https://api.openai.com/dashboard/user
Authorization: Bearer <access_token>
Content-Type: application/json

{"name": "API User"}

# 2. 创建 onboarding session
POST https://api.openai.com/dashboard/onboarding/session
Authorization: Bearer <access_token>
```

---

### Step 8：UpgradePlusStep（升级 Plus — 跳过）

**文件**：`backend/src/steps/upgrade.py`

```
输入：无
操作：检查 settings.registration.skip_upgrade_plus
输出：skip_reason="Plus upgrade skipped by configuration"
```

当前配置默认跳过 Plus 升级。

---

## 数据流总结

```
Step 1: TalentMail → mailbox_id, email
                         ↓
Step 2: Patchright → browser_session (in metadata)
                         ↓
Step 3: TalentMail → verification_code
                         ↓
Step 4: Patchright → authorization_code, code_verifier (in metadata)
                         ↓
Step 5: (跳过)
                         ↓
Step 6: OpenAI API → access_token, refresh_token
                         ↓
Step 7: OpenAI API → account_info
                         ↓
Step 8: (跳过)
                         ↓
AccountStore → 保存到 accounts.db（密码 Fernet 加密）
```

---

## 不可变 Pipeline Context

所有步骤通过 `PipelineContext`（frozen dataclass）传递数据。每个步骤返回 `StepResult.data`，由 Runner 合并到新的 Context 中：

```python
# 不可变！每次 set 返回新对象
new_context = context.set("email", "abc@talenting.vip")
new_context = new_context.set("mailbox_id", "123")
```

**关键字段**：
| 字段 | 类型 | 设置步骤 | 用途 |
|------|------|----------|------|
| `email` | str | Step 1 | 注册邮箱 |
| `password` | str | 初始 | 注册密码 |
| `mailbox_id` | str | Step 1 | TalentMail 邮箱 ID |
| `verification_code` | str | Step 3 | 6 位验证码 |
| `access_token` | str | Step 6 | OpenAI Bearer token |
| `refresh_token` | str | Step 6 | Token 刷新凭证 |
| `account_info` | dict | Step 7 | 账户完整信息 |

**Metadata 字段**（浏览器/OAuth 相关）：
| 字段 | 设置步骤 | 用途 |
|------|----------|------|
| `_browser_manager` | Step 2 | Patchright 管理器实例 |
| `browser_session_id` | Step 2 | 浏览器会话 ID |
| `_active_page` | Step 2 | 活跃页面对象 |
| `authorization_code` | Step 4 | OAuth 授权码 |
| `code_verifier` | Step 4 | PKCE 验证器 |
| `oauth_state` | Step 4 | CSRF state |

---

## 关键配置

```yaml
# backend/config/settings.yaml

openai:
  auth_url: "https://auth.openai.com"
  authorize_url: "https://auth.openai.com/authorize"
  register_callback_url: "http://localhost:1455/auth/callback"
  oauth_client_id: "app_EMoamEEZ73f0CkXaXp7hrann"
  token_url: "https://auth0.openai.com/oauth/token"
  default_password: "自动生成或配置"
  timeout_seconds: 120.0

registration:
  skip_phone_verification: true
  skip_upgrade_plus: true
  profile_name: "API User"
  headless: false             # 必须 false（Cloudflare）
  browser_timeout: 30
  typing_delay_ms: 150
  navigation_timeout: 60

talentmail:
  base_url: "https://mail.talenting.vip/api"
  email: "test-register@talenting.vip"
  password: "123456"
```

---

## 外部依赖

| 依赖 | 用途 | 必须 |
|------|------|------|
| TalentMail | 临时邮箱创建 + 验证码接收 | Step 1, 3 |
| Patchright | 浏览器自动化（绕过 Cloudflare） | Step 2, 4 |
| Xvfb | 云端虚拟显示（headed 模式需要） | 云端部署 |
| OpenAI auth.openai.com | OAuth 授权 | Step 4 |
| OpenAI auth0.openai.com | Token 交换 | Step 6 |
| OpenAI api.openai.com | Dashboard API | Step 7 |

---

## 已知问题与限制

1. **Cloudflare 强制 headed 模式**：Patchright 必须用 headed 模式，云端需要 Xvfb
2. **authorization_code 有效期短**：Step 4-6 必须快速连续执行
3. **OpenAI 注册页面 DOM 可能变化**：Step 2 的 CSS 选择器可能需要更新
4. **TalentMail mail_sync 30 秒延迟**：Step 3 最快也要等 30 秒才能拿到验证码
5. **临时邮箱域名可能被 OpenAI 封禁**：如果 `talenting.vip` 被标记为可疑域名

---

**文档路径**：`docs/REGISTRATION_FLOW.md`
