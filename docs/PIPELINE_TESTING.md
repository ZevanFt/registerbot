# 注册流水线测试指南

**更新日期**：2026-03-04
**前置条件**：TalentMail 云端已部署 Dovecot SQL UNION 修复（临时邮箱收邮件）

---

## 测试环境准备

### 1. 后端服务

```bash
cd /home/talent/projects/register-bot/backend
source .venv/bin/activate
python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### 2. TalentMail 服务

确认 TalentMail 所有容器运行正常：

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep talentmail
```

5 个容器都应为 `Up` 状态：backend、frontend、caddy、mailserver、db。

### 3. 配置检查

确认 `backend/config/settings.yaml` 中 TalentMail 配置正确：

```yaml
talentmail:
  base_url: "https://mail.talenting.vip/api"   # 云端用域名
  email: "test-register@talenting.vip"
  password: "123456"
```

---

## 分步测试

### 测试 1：TalentMail 连通性

**目的**：验证 register-bot 能访问 TalentMail API。

```bash
curl -s -X POST 'https://mail.talenting.vip/api/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test-register@talenting.vip","password":"123456"}' \
  | python3 -m json.tool
```

**通过标准**：返回包含 `access_token` 的 JSON。

---

### 测试 2：创建临时邮箱（Step 1）

**目的**：验证 Pool API 能创建临时邮箱。

```bash
# 通过 register-bot API 测试（只跑 Step 1）
curl -s -X POST 'http://localhost:8001/api/pipeline/register' \
  -H 'Content-Type: application/json' \
  -d '{}' &
# 注意：这会启动完整流水线，观察日志中 Step 1 结果即可

# 或者直接调用 TalentMail API 测试
TOKEN=$(curl -s -X POST 'https://mail.talenting.vip/api/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test-register@talenting.vip","password":"123456"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST 'https://mail.talenting.vip/api/pool/' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"prefix":"pipetest"}' \
  | python3 -m json.tool
```

**通过标准**：返回包含 `id` 和 `email`（如 `pipetest@talenting.vip`）的 JSON。

---

### 测试 3：临时邮箱收邮件（Step 3 前提）

**目的**：验证 Dovecot UNION 修复后临时邮箱能收到邮件。

```bash
# 1. 获取刚创建的临时邮箱地址
MAILBOX_EMAIL="pipetest@talenting.vip"

# 2. 从外部发送测试邮件（模拟 OpenAI 发验证邮件）
python3 -c "
import smtplib
from email.mime.text import MIMEText

msg = MIMEText('Your verification code is 654321')
msg['Subject'] = 'OpenAI - Verify your email 654321'
msg['From'] = 'noreply@openai.com'
msg['To'] = '${MAILBOX_EMAIL}'

smtp = smtplib.SMTP('maillink.talenting.vip', 25, timeout=30)
smtp.ehlo()
smtp.starttls()
smtp.ehlo()
smtp.sendmail('noreply@openai.com', '${MAILBOX_EMAIL}', msg.as_string())
smtp.quit()
print('Sent OK')
"

# 3. 等待 mail_sync 同步（30 秒）
sleep 35

# 4. 通过 Pool API 查看收件箱
MAILBOX_ID=<上一步返回的id>
curl -s "https://mail.talenting.vip/api/pool/${MAILBOX_ID}/emails" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

**通过标准**：
- SMTP 发送返回 `Sent OK`
- Pool API 返回邮件列表包含测试邮件
- 邮件内容包含 `654321`

**失败排查**：
- 如果 SMTP 超时：检查云服务器 25 端口是否开放
- 如果邮件列表为空：检查 Dovecot 日志 `docker compose logs mailserver | grep -i 'pipetest'`
- 如果 IMAP 同步失败：检查 master user 配置 `docker compose exec mailserver doveadm auth test -x service=imap "pipetest@talenting.vip*sync_master" "SyncMasterPassword123"`

---

### 测试 4：完整流水线测试

**目的**：端到端验证 8 步注册流水线。

**前置条件**：
- Xvfb 已启动（云端无头模式需要虚拟显示）：`Xvfb :99 -screen 0 1280x720x24 &`
- `DISPLAY=:99` 环境变量已设置
- Patchright 浏览器已安装：`python -m patchright install chromium`

```bash
# 启动完整注册流程
curl -s -X POST 'http://localhost:8001/api/pipeline/register' \
  -H 'Content-Type: application/json' \
  -d '{}' \
  | python3 -m json.tool
```

**观察后端日志**：

```bash
# 另一个终端
tail -f /tmp/register-bot.log  # 或查看 uvicorn 输出
```

**期望的步骤执行序列**：

| 步骤 | 名称 | 期望结果 | 耗时预估 |
|------|------|----------|----------|
| 1 | CreateTempEmailStep | 成功，返回 mailbox_id + email | < 3s |
| 2 | BrowserSignupStep | 成功，浏览器填写注册表单 | 30-120s |
| 3 | WaitForVerificationCodeStep | 成功，从 TalentMail 获取 6 位验证码 | 30-300s |
| 4 | BrowserVerifyEmailStep | 成功，输入验证码 + PKCE OAuth | 10-30s |
| 5 | VerifyPhoneStep | 跳过（skip_phone_verification=true） | < 1s |
| 6 | SetPasswordStep | 成功，token exchange | < 5s |
| 7 | SetProfileStep | 成功，设置用户名 | < 5s |
| 8 | UpgradePlusStep | 跳过（skip_upgrade_plus=true） | < 1s |

**通过标准**：

```json
{
  "success": true,
  "steps_completed": 8,
  "steps_failed": 0,
  "total_duration": "...",
  "email": "xxx@talenting.vip"
}
```

---

## 单步测试（DevPipeline）

前端 DevPipeline 页面支持单步执行和调试：

1. 打开浏览器访问 `http://localhost:5173`（前端开发服务器）
2. 导航到「开发流水线」页面
3. 可以逐步执行每个 Step，观察中间状态

---

## 常见失败场景与排查

### Step 2 失败：浏览器超时

```
error: "Timed out waiting for password field"
```

**排查**：
- Cloudflare 拦截：检查是否用的 Patchright（不是 Playwright）
- Xvfb 未启动：`ps aux | grep Xvfb`
- 页面改版：OpenAI 注册页面 DOM 结构可能已变化

### Step 3 失败：验证码超时

```
error: "Timeout waiting for verification code"
```

**排查**：
1. 检查 OpenAI 是否真的发了邮件（查看 OpenAI 注册页面是否显示 "Check your inbox"）
2. 检查 TalentMail 是否收到邮件：
   ```bash
   docker compose exec mailserver doveadm mailbox status messages INBOX -u <邮箱地址>
   ```
3. 如果 Dovecot 收到了但 API 没有：检查 mail_sync 日志
4. 如果 Dovecot 也没收到：检查 Postfix 队列 `docker compose exec mailserver postqueue -p`

### Step 4 失败：PKCE 授权失败

```
error: "Failed to capture authorization code"
```

**排查**：
- 验证码是否正确（6 位数字）
- OAuth redirect_uri 是否匹配（`http://localhost:1455/auth/callback`）
- 浏览器 session 是否还活着（超时可能导致 session 断开）

### Step 6 失败：Token Exchange

```
error: "Token exchange failed: 401"
```

**排查**：
- authorization_code 是否过期（有效期很短）
- code_verifier 是否和 Step 4 的 code_challenge 匹配
- client_id 是否正确（`app_EMoamEEZ73f0CkXaXp7hrann`）

---

## 测试检查清单

- [ ] TalentMail API 连通（login 成功）
- [ ] 创建临时邮箱成功
- [ ] 临时邮箱能接收 SMTP 邮件
- [ ] mail_sync 能同步临时邮箱到 PostgreSQL
- [ ] Pool API 能读取临时邮箱中的邮件
- [ ] 验证码提取正则匹配（6 位数字）
- [ ] 浏览器自动化能打开 chatgpt.com
- [ ] 完整 8 步流水线执行成功
- [ ] 注册成功后账户保存到 accounts.db

---

**文档路径**：`docs/PIPELINE_TESTING.md`
