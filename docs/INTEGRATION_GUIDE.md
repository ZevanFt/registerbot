# codex2api - 联调操作指南

## 部署拓扑

```
本地开发机                          云服务器
┌─────────────┐                   ┌──────────────────┐
│ Frontend    │ ←── HTTP ───→     │                  │
│ :5173       │                   │  TalentMail      │
│             │                   │  (邮件服务)       │
│ Backend     │ ──── HTTPS ──→    │  http://你的IP:端口│
│ :8000       │                   │                  │
└─────────────┘                   └──────────────────┘
       │
       │ HTTPS (需要代理/直连)
       ▼
┌─────────────┐
│ OpenAI API  │
│ api.openai  │
│ .com        │
└─────────────┘
```

**本地开发完全可以联调！** 只要：
1. 本地能访问云服务器的 TalentMail API
2. 本地能访问 api.openai.com（可能需要代理）
3. 配置 `settings.yaml` 中的 `talentmail.base_url` 为云服务器地址

## 前置准备

### 1. 环境要求
- Python 3.12+
- Node.js 18+
- pnpm / npm

### 2. 安装依赖

```bash
# 后端
cd backend
python -m venv .venv
.venv/bin/python -m pip install -e .

# 前端
cd frontend
npm install
```

### 3. 配置文件

后端配置位于 `backend/config/settings.yaml`（首次启动自动生成默认值）。

关键配置项：
```yaml
admin:
  username: admin-zevan
  password: adminpassword-zevan
  jwt_secret: change-me-in-production  # 生产环境必须改为 32+ 字节随机串

openai:
  base_url: https://api.openai.com   # 上游 API 地址
  auth_url: https://auth0.openai.com  # OAuth2 认证地址
  oauth_client_id: ''          # 需抓包填入
  oauth_client_secret: ''      # 需抓包填入
  turnstile_sitekey: ''        # Cloudflare Turnstile
  default_password: ''         # 批量注册默认密码
  timeout_seconds: 120
  stream_timeout_seconds: 300

talentmail:
  base_url: https://mail.talenting.vip/api
  email: test-register@talenting.vip
  password: '123456'

network:
  http_proxy: ''               # 全局代理 (如 socks5://127.0.0.1:7897)
  openai_proxy: ''             # OpenAI 专用代理 (优先于 http_proxy)
  talentmail_proxy: ''         # TalentMail 专用代理

proxy:
  cooldown_seconds: 60
  failure_threshold: 3
  health_check_interval_seconds: 30
  token_refresh_enabled: true
  token_refresh_interval_seconds: 30
  token_refresh_skew_seconds: 300

registration:
  skip_phone_verification: true
  skip_upgrade_plus: true
  profile_name: API User
  max_concurrent_registrations: 1

storage:
  db_path: data/accounts.db
  tokens_db_path: data/tokens.db
  stats_db_path: data/stats.db
  encryption_key: ''           # 首次启动自动生成
```

---

## 启动服务

### 终端 1: 后端

```bash
cd backend
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后：
- 管理 API: http://localhost:8000/api/
- OpenAI 代理: http://localhost:8000/v1/
- API 文档: http://localhost:8000/docs

### 终端 2: 前端

```bash
cd frontend
npx vite dev
```

前端启动后：
- Dashboard: http://localhost:5173/

---

## 联调步骤

### Step 1: 验证管理端登录

```bash
# 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'

# 返回: {"token":"eyJ...", "username":"admin"}
# 保存 token 到变量
export ADMIN_TOKEN="eyJ..."

# 验证
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Step 2: 创建 API 令牌

```bash
# 创建令牌
curl -X POST http://localhost:8000/api/tokens \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"test-token"}'

# 返回: {"id":1, "name":"test-token", "key":"sk-xxxx...", ...}
export API_KEY="sk-xxxx..."
```

### Step 3: 手动添加测试账号

在真实注册流程跑通之前，可以手动添加账号来测试代理功能：

```bash
# 创建账号（需要真实的 OpenAI access_token）
curl -X POST http://localhost:8000/api/accounts \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "test@example.com",
    "password": "test123",
    "status": "active",
    "openai_token": "YOUR_REAL_OPENAI_ACCESS_TOKEN"
  }'
```

> **如何获取 access_token**: 在浏览器中登录 ChatGPT，打开 DevTools → Application → Cookies/Local Storage，找到 access_token。或通过 Network 面板捕获 `/api/auth/session` 响应。

### Step 4: 测试 API 代理

```bash
# 查询模型
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer $API_KEY"

# 非流式对话
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4",
    "messages": [{"role":"user","content":"Hello!"}]
  }'

# 流式对话
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4",
    "messages": [{"role":"user","content":"Hello!"}],
    "stream": true
  }'
```

### Step 5: 测试注册流水线 (需要先配置好 OAuth 参数)

```bash
# 触发注册
curl -X POST http://localhost:8000/api/pipeline/register \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": null,
    "password": null
  }'
# email=null 时自动创建临时邮箱
# password=null 时使用 settings.openai.default_password

# 查看注册状态
curl http://localhost:8000/api/pipeline/status \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Step 6: 用 OpenAI SDK 验证兼容性

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-xxxx...",           # 你创建的 API 令牌
    base_url="http://localhost:8000/v1"
)

# 非流式
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# 流式
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

---

## 监控与调试

### 方式 1: DevTools 可视化面板 (推荐)

登录后台后，侧边栏「开发工具」分组提供 3 个实时页面：

| 页面 | 路径 | 用途 |
|------|------|------|
| **实时日志** | `/#/dev/logs` | WebSocket 实时推送，支持暂停/过滤/搜索，可切换到历史标签查归档 |
| **流水线** | `/#/dev/pipeline` | 8 步注册流水线可视化，实时状态+耗时，一键触发注册 |
| **测试面板** | `/#/dev/test` | 一键运行 pytest，终端风格实时输出，PASSED 绿色/FAILED 红色 |

### 方式 2: curl 命令行

```bash
# 查询日志
curl "http://localhost:8000/api/logs?level=ALL&source=ALL&page=1&limit=20" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 按级别过滤
curl "http://localhost:8000/api/logs?level=ERROR" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 历史日志文件列表
curl http://localhost:8000/api/devtools/logs/files \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 读取某天的历史日志
curl "http://localhost:8000/api/devtools/logs/history?file=2026-03-03.jsonl&offset=0&limit=50" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### 查看统计

```bash
# 今日汇总
curl http://localhost:8000/api/stats/summary \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 小时分布
curl "http://localhost:8000/api/stats/hourly?date=2026-03-03" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 模型分布
curl http://localhost:8000/api/stats/models \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### 查看账号健康状态

```bash
curl http://localhost:8000/api/accounts \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl http://localhost:8000/api/dashboard/stats \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 运行测试

### 方式 1: DevTools 测试面板 (推荐)

打开 `/#/dev/test`，点击「运行全部测试」，实时查看输出。

### 方式 2: 命令行

```bash
cd backend

# 全量测试
.venv/bin/python -m pytest tests/ -v

# 单个文件
.venv/bin/python -m pytest tests/test_openai_proxy.py -v

# 前端类型检查 + 构建
cd frontend
npx vue-tsc --noEmit
npx vite build
```

---

## 网络连通性检查

联调前请确保以下网络连通：

```bash
# 1. 本地 → TalentMail 云服务器
curl -s http://你的云服务器地址/api/health
# 应返回 200 或服务信息

# 2. 本地 → OpenAI API（可能需要代理）
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer sk-your-test-key"
# 返回模型列表或 401（都说明网络通了）

# 3. 前端 → 后端
curl -s http://localhost:8000/docs
# 应返回 FastAPI 文档页面
```

如果本地无法直连 OpenAI，需要配置代理。注意：代码中 httpx 使用了 `trust_env=False`，
所以环境变量的代理不会生效。如果需要代理，有两种方案：

**方案 A**: 使用系统透明代理（如 clash TUN 模式 / tun2socks）
- 不需要改代码，所有流量自动走代理

**方案 B**: 修改 `openai.base_url` 指向代理中转服务
- 例如用 one-api 等中转服务
- 配置 `settings.yaml` 中 `openai.base_url` 指向中转地址

---

## 常见问题

### Q: httpx 报 SOCKS 代理错误
**A**: 代码中已统一使用 `trust_env=False`，如果仍有问题，检查是否有新增的 httpx 调用遗漏了此参数。

### Q: 前端登录后白屏
**A**: 检查后端 CORS 配置（`app.py` 中 `allow_origins`），确保包含前端地址 `http://localhost:5173`。

### Q: API 代理返回 503 "no active account available"
**A**: 需要先添加 status=active 且有 openai_token 的账号。参见 Step 3。

### Q: JWT InsecureKeyLengthWarning
**A**: 测试中的短 secret 会触发警告，正常。生产环境修改 `admin.jwt_secret` 为 32+ 字节随机串。

### Q: 注册流水线报 NotImplementedError
**A**: 检查 OAuth 参数是否已填入 settings.yaml，以及 TalentMail 服务是否启动。

### Q: 本地无法连接云端 TalentMail
**A**: 检查：
1. 云服务器防火墙是否放通了 TalentMail 端口
2. `settings.yaml` 中 `talentmail.base_url` 是否正确（含协议和端口）
3. `curl http://云服务器地址:端口/api/health` 是否通

### Q: WebSocket 连接失败
**A**: 检查：
1. 后端是否启动（`uvicorn app:app`）
2. 浏览器控制台是否有 CORS 错误
3. WebSocket URL 中 `?token=` 参数是否传了 admin JWT token

### Q: 测试面板运行报错 "already running"
**A**: 同一时刻只允许一个测试运行。等上一个完成或刷新页面。
