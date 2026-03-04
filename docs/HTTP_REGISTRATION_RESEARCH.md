# 纯 HTTP 注册方案调研

> 2026-03-05 调研完成

## 10 步纯 HTTP 注册流程（逆向推演）

基于朋友截图 + 开源项目 + 现有代码分析：

| Step | 动作 | 端点 | 我们已有？ |
|------|------|------|-----------|
| 1 | GET chatgpt.com 拿 CSRF + cookies | `GET https://chatgpt.com/` (Next-Auth) | ❌ |
| 2 | POST signin 拿 authorize URL | `POST https://chatgpt.com/api/auth/signin/login-web` | ❌ |
| 3 | GET auth0 authorize (prompt=signup) | `GET https://auth0.openai.com/authorize?...&prompt=signup` | ✅ `init_auth_session()` |
| 4 | POST 邮箱 | `POST https://auth0.openai.com/u/signup/identifier` | ✅ `check_email_available()` |
| 5 | POST 密码 | `POST https://auth0.openai.com/u/signup` | ✅ `submit_registration()` |
| 6 | 解 Turnstile | Capsolver API / 本地 Patchright solver | ❌ |
| 7 | 等验证码 | TalentMail 轮询 | ✅ `WaitForVerificationCodeStep` |
| 8 | POST 验证码 | `POST https://auth0.openai.com/u/signup/verify` | ✅ `verify_email()` |
| 9 | POST name + birthday | `POST https://auth.openai.com/create-account/about-you` | ❌ |
| 10 | 换 token | `POST https://auth0.openai.com/oauth/token` (PKCE) | ✅ `exchange_code_for_tokens()` |

**已实现 5/10 步**，缺 Step 1, 2, 6, 9 和 Next-Auth 层。

## Turnstile 解法对比

| 方案 | 费用 | 速度 | 适合 |
|------|------|------|------|
| CapSolver | $1.2/千次 | 5-10s | 生产环境，稳定快速 |
| 2Captcha | $1.45/千次 | 10-20s | 备选 |
| Anti-Captcha | $2.0/千次 | 10-15s | 备选 |
| **BotsForge/CloudFlare** (自建) | **免费** | 4-6s | 开发/小规模，用 Patchright |
| Theyka/Turnstile-Solver | 免费 | 4-6s | 同上 |

### BotsForge 方案详情

- GitHub: https://github.com/BotsForge/CloudFlare
- Capsolver 兼容 API (`POST /createTask` + `POST /getTaskResult`)
- 自托管 `http://localhost:5033`
- 用 Patchright 浏览器只解 Turnstile widget（4-6 秒）
- 我们已有 Patchright 依赖，零额外成本

## 开源参考项目

| 项目 | 链接 | 状态 | 说明 |
|------|------|------|------|
| acheong08/OpenAIAuth | github.com/acheong08/OpenAIAuth | 归档 | Auth0 登录流程，用 tls_client |
| rawandahmad698/PyChatGPT | github.com/rawandahmad698/PyChatGPT | 过时 | Auth0 login 逆向 |
| BHPT-VIP/ChatGPTAccountCreator | github.com/BHPT-VIP/ChatGPTAccountCreator | 不确定 | 批量注册脚本 |
| xtekky/gpt4free | github.com/xtekky/gpt4free | 活跃 | 含 Turnstile 处理 |

## 技术注意事项

1. **TLS 指纹**: httpx 的 TLS 指纹和浏览器不同，Cloudflare JA3/JA4 可识别。可能需要 `curl_cffi` 或 `tls_client`
2. **Next-Auth CSRF**: chatgpt.com 用 NextAuth.js，CSRF 用 double-submit cookie (`__Host-next-auth.csrf-token`)
3. **Auth0 State**: JWT 编码的 state token 跨多次重定向传递，每步依赖上一步
4. **流程变更风险**: OpenAI 可能随时改注册流程

## 实施建议

1. **短期**: 先修好浏览器注册，验证完整闭环
2. **中期**: 纯 HTTP + BotsForge Turnstile（免费），50 并发
3. **长期**: 评估 Capsolver（$1.2/千次），更快更稳
