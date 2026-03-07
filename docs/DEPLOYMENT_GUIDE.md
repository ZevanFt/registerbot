# codex2api - 部署指南

> 文档级别: `P0 / 最高优先级`
> 
> 本文档是部署与联调的单一事实源（SSOT）。当其他文档出现端口、启动命令或登录路径不一致时，以本文档为准。

## 当前基线 (2026-03-07)

- 前端开发端口: `5173` (`http://localhost:5173/#/login`)
- 后端 API 端口: `8001` (`http://localhost:8001`)
- chat2api 端口: `5005` (`http://localhost:5005`)
- 前端登录请求: `POST http://localhost:8001/api/auth/login`
- 管理端登录来源: `users` 表（非账号池 `accounts` 表）

### 关键链路（登录）

1. 浏览器访问 `http://localhost:5173/#/login`
2. 前端读取 `frontend/.env.development` 中 `VITE_API_BASE_URL=http://localhost:8001/api`
3. 前端请求 `POST http://localhost:8001/api/auth/login`
4. 后端在 `backend/data/accounts.db` 的 `users` 表校验账号密码并签发 JWT

## 两个阶段

### 阶段 1: 本地开发联调

```
本地电脑                              云服务器
┌────────────────┐                  ┌──────────────────┐
│ Frontend :5173 │                  │                  │
│ Backend  :8001 │───── HTTP ──────▶│ TalentMail :端口  │
└────────────────┘                  └──────────────────┘
        │
        │ HTTPS (需代理)
        ▼
   OpenAI API
```

- 后端通过网络访问云端 TalentMail
- 后端通过代理访问 OpenAI API
- 前后端都在本地

### 阶段 2: 云端正式部署 (目标)

```
云服务器 (同一台机器)
┌───────────────────────────────────────────────┐
│                                               │
│  Nginx (反向代理, :80/:443)                    │
│  ├── /          → Frontend 静态文件            │
│  ├── /api/*     → Backend :8001               │
│  ├── /v1/*      → Backend :8001               │
│  └── /ws/*      → Backend :8001 (WebSocket)   │
│                                               │
│  Backend (uvicorn :8001)                      │
│  ├── API 代理、管理、Pipeline                  │
│  └── 直接访问 localhost TalentMail (同机!)     │
│                                               │
│  TalentMail (:已有端口)                        │
│  └── 邮件服务 (已部署运行中)                    │
│                                               │
└───────────────────────────────────────────────┘
        │
        │ HTTPS
        ▼
   OpenAI API
```

**同机部署的优势：**
- TalentMail 直接走 localhost，零延迟、无需开放端口
- Nginx 统一入口，SSL 只配一处
- 同一台机器管理简单

---

## 阶段 1: 本地联调配置

### settings.yaml 配置

```yaml
admin:
  username: admin-zevan
  password: adminpassword-zevan
  jwt_secret: change-me-in-production  # 生产环境用 python -c "import secrets; print(secrets.token_hex(32))" 生成
  jwt_expire_hours: 24

openai:
  base_url: https://api.openai.com   # 或代理地址
  auth_url: https://auth0.openai.com
  token_url: https://auth0.openai.com/oauth/token
  register_callback_url: https://platform.openai.com/auth/callback
  oauth_client_id: ''                # 待填: 抓包获取
  oauth_client_secret: ''            # 待填: 抓包获取
  turnstile_sitekey: ''              # 待填: 抓包获取
  default_password: ''               # 批量注册默认密码
  timeout_seconds: 120
  stream_timeout_seconds: 300

talentmail:
  base_url: https://mail.talenting.vip/api   # TalentMail API 地址
  email: test-register@talenting.vip
  password: '123456'

network:
  http_proxy: ''                     # 全局代理
  openai_proxy: ''                   # OpenAI 专用代理 (优先于 http_proxy)
  talentmail_proxy: ''               # TalentMail 专用代理

proxy:
  cooldown_seconds: 60
  failure_threshold: 3
  health_check_interval_seconds: 30
  token_refresh_enabled: true
  token_refresh_interval_seconds: 30
  token_refresh_skew_seconds: 300
  token_refresh_timeout_seconds: 15.0
  token_refresh_max_retries: 3
  token_refresh_backoff_seconds: 60

registration:
  skip_phone_verification: true
  skip_upgrade_plus: true
  profile_name: API User
  mode: browser                    # browser 或 http
  http_turnstile_token: ''         # 纯 HTTP 注册验证码 token（可空）
  http_require_turnstile: false    # true 时未配置 token 将直接失败
  max_concurrent_registrations: 1

storage:
  db_path: data/accounts.db
  tokens_db_path: data/tokens.db
  stats_db_path: data/stats.db
  encryption_key: ''                 # 首次启动自动生成
```

### 启动命令

```bash
# 终端 1: 后端
cd backend
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8001 --reload

# 终端 2: 前端
cd frontend
npx vite dev
```

### 联调检查清单

- [ ] TalentMail 云端可达: `curl http://云IP:端口/api/health`
- [ ] OpenAI API 可达: `curl https://api.openai.com/v1/models` (可能需代理)
- [ ] 后端启动: `curl http://localhost:8001/docs`
- [ ] 前端启动: 浏览器打开 `http://localhost:5173`
- [ ] 登录成功: 使用初始化脚本设置的管理员账号
- [ ] 创建 API Token: 令牌管理页面
- [ ] 添加测试账号 (手动): 账号管理页面

---

## 阶段 2: 云端部署

### 2.1 服务器准备

```bash
# 安装 Python 3.12
sudo apt update
sudo apt install python3.12 python3.12-venv

# 安装 Node.js 18+ (用于构建前端, 部署后不需要)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo bash -
sudo apt install nodejs

# 安装 Nginx
sudo apt install nginx
```

### 2.2 上传代码

```bash
# 本地打包 (排除 node_modules, .venv, dist 等)
cd /path/to/register-bot
tar czf register-bot.tar.gz \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='dist' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='data/*.db' \
  backend/ frontend/ docs/ scripts/

# 上传到服务器
scp register-bot.tar.gz user@云IP:/opt/

# 服务器端解压
ssh user@云IP
cd /opt
tar xzf register-bot.tar.gz
```

### 2.3 后端部署

```bash
cd /opt/register-bot/backend

# 创建虚拟环境
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .

# 创建数据目录
mkdir -p data data/logs

# 编辑配置 (关键改动!)
vim config/settings.yaml

# 回到项目根目录，初始化管理员（推荐）
cd /opt/register-bot
./scripts/dev_stack.sh init-admin
```

**云端 settings.yaml 关键差异：**

```yaml
admin:
  jwt_secret: 用 python -c "import secrets; print(secrets.token_hex(32))" 生成

talentmail:
  base_url: http://localhost:TalentMail端口    # ← 同机! 用 localhost

openai:
  base_url: https://api.openai.com   # 云端能否直连? 需确认
```

### 2.3.1 管理员初始化脚本（推荐，交互式）

```bash
cd /opt/register-bot
./scripts/dev_stack.sh init-admin
```

脚本会交互提问并写入：
- `backend/config/settings.yaml` 的 `admin.username/admin.password/admin.jwt_secret`
- `backend/data/accounts.db` 的 `users` 表（创建或更新管理员用户）

非交互模式（CI 或自动化）：

```bash
cd /opt/register-bot
./scripts/dev_stack.sh init-admin \
  --non-interactive \
  --username admin \
  --password 'YourStrongPass123!' \
  --email 'admin@example.com'
```

说明：
- `email` 非必填
- `jwt_secret` 不传时自动生成
- 脚本会将该用户权限强制为 `admin`

### 2.4 前端构建

```bash
cd /opt/register-bot/frontend

# 安装依赖并构建
npm install
npx vite build

# 构建产物在 dist/ 目录
ls dist/
# index.html  assets/
```

### 2.5 systemd 服务

创建 `/etc/systemd/system/codex2api.service`:

```ini
[Unit]
Description=codex2api Backend
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/opt/register-bot/backend
ExecStart=/opt/register-bot/backend/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable codex2api
sudo systemctl start codex2api
sudo systemctl status codex2api
```

### 2.6 Nginx 配置

创建 `/etc/nginx/sites-available/codex2api`:

```nginx
server {
    listen 80;
    server_name 你的域名或IP;

    # 前端静态文件
    root /opt/register-bot/frontend/dist;
    index index.html;

    # SPA hash 路由 — 所有未匹配路径返回 index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 管理 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # OpenAI 兼容 API 代理
    location /v1/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;  # 流式请求需要长超时
        proxy_buffering off;      # SSE 不缓冲
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $websocket_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;  # WebSocket 长连接
    }
}

# WebSocket upgrade 映射
map $http_upgrade $websocket_upgrade {
    default upgrade;
    '' close;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/codex2api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

> 可选：如果你使用 Caddy 而不是 Nginx（推荐云端使用 `codex.talenting.vip`），请直接运行：
>
> ```bash
> cd /opt/register-bot
> bash scripts/deploy_cloud_caddy.sh --domain codex.talenting.vip --email you@talenting.vip
> ```
>
> 详细说明见 [CADDY 部署文档](./CADDY_DEPLOYMENT.md) 和 [Caddyfile 示例](./Caddyfile.codex.example)。

### 2.7 HTTPS (可选但推荐)

```bash
# 用 certbot 自动配置 Let's Encrypt SSL
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
```

启用 HTTPS 后，前端 `api/client.ts` 的 base URL 会自动匹配（相对路径）。

### 2.8 部署后检查

```bash
# 后端服务状态
sudo systemctl status codex2api

# 后端日志
sudo journalctl -u codex2api -f

# Nginx 状态
sudo systemctl status nginx

# 测试 API
curl http://localhost:8001/docs
curl http://你的域名/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"你的密码"}'

# 测试 OpenAI 代理
curl http://你的域名/v1/models \
  -H "Authorization: Bearer sk-xxx"
```

---

## 前端 API 地址适配

当前前端 `api/client.ts` 在开发环境请求 `http://localhost:8001`，部署后建议改为相对路径。

**方案：环境变量控制**

`frontend/.env.development`:
```
VITE_API_BASE_URL=http://localhost:8001
```

`frontend/.env.production`:
```
VITE_API_BASE_URL=
```

`frontend/src/api/client.ts` 中使用:
```typescript
const BASE = import.meta.env.VITE_API_BASE_URL || ''
```

开发时请求 `http://localhost:8001/api/...`，
生产时请求 `/api/...`（Nginx 代理到后端）。

---

## 更新部署

后续代码更新时的操作流程：

```bash
# 1. 本地构建前端
cd frontend && npx vite build

# 2. 打包上传
tar czf update.tar.gz \
  --exclude='.venv' --exclude='node_modules' \
  --exclude='__pycache__' --exclude='data' \
  backend/ frontend/dist/

scp update.tar.gz user@云IP:/tmp/

# 3. 服务器端更新
ssh user@云IP
cd /opt/register-bot
tar xzf /tmp/update.tar.gz

# 4. 更新后端依赖 (如有新增)
cd backend && .venv/bin/python -m pip install -e .

# 5. 重启后端
sudo systemctl restart codex2api

# 不需要重启 Nginx (静态文件直接生效)
```

---

## 纯 HTTP 注册联调（云端推荐）

1. 在 `backend/config/settings.yaml` 设置：
```yaml
registration:
  mode: http
  http_turnstile_token: ''
  http_require_turnstile: false
```

2. 调试接口（管理员权限）：
```bash
curl -X POST http://127.0.0.1:8001/api/devtools/registration/http-test \
  -H 'Authorization: Bearer <ADMIN_JWT>' \
  -H 'Content-Type: application/json' \
  -d '{
    "target": 3,
    "max_failures": 3,
    "delay_seconds": 2.0,
    "turnstile_token": ""
  }'
```

3. 验收建议：
- 先跑 `target=3` 看错误分布
- 再跑 `target=10` 看成功率和稳定性
- 若大量出现风控错误，再引入真实 turnstile token 提供方

---

## 数据备份

```bash
# 备份数据库和配置
tar czf backup-$(date +%Y%m%d).tar.gz \
  /opt/register-bot/backend/data/ \
  /opt/register-bot/backend/config/settings.yaml

# 定时备份 (crontab)
0 3 * * * tar czf /opt/backups/codex2api-$(date +\%Y\%m\%d).tar.gz /opt/register-bot/backend/data/ /opt/register-bot/backend/config/settings.yaml
```

---

## 端口规划 (同一台云服务器)

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx | 80/443 | 统一入口, HTTPS |
| codex2api Backend | 8001 | 仅监听 127.0.0.1, 不对外暴露 |
| TalentMail | 原有端口 | 已部署, Backend 通过 localhost 访问 |

**安全提醒：** 后端 uvicorn 监听 `127.0.0.1:8001`（不是 `0.0.0.0`），
外部只能通过 Nginx 访问，防止绕过 Nginx 直接打后端。
