# Caddy 部署说明（codex 子域）

> 目标：使用 `codex.talenting.vip` 作为统一入口，转发到本机前端静态文件和 `backend:8001`。
> 本文档只用于云端部署，本地开发不需要 Caddy。

## 1. 推荐：使用一键脚本（云端）

```bash
cd /opt/register-bot
bash scripts/deploy_cloud_caddy.sh --domain codex.talenting.vip --email you@talenting.vip
```

脚本会自动执行：
- 安装 Caddy（若未安装）
- 生成并写入 `/etc/caddy/Caddyfile`
- 校验配置并重启 Caddy

## 2. 手动部署（可选）

### 2.1 安装 Caddy（Ubuntu）

```bash
sudo apt update
sudo apt install -y caddy
```

### 2.2 准备前后端

```bash
cd /opt/register-bot/frontend
npm install
npm run build

cd /opt/register-bot
./scripts/dev_stack.sh down
./scripts/dev_stack.sh up
```

建议后端生产态改为 systemd 托管，保持监听 `127.0.0.1:8001`。

### 2.3 配置域名

将 `codex.talenting.vip` 的 DNS A 记录指向云服务器公网 IP。

### 2.4 配置 Caddy

1. 复制示例：

```bash
sudo cp /opt/register-bot/docs/Caddyfile.codex.example /etc/caddy/Caddyfile
```

2. 修改：
- `email admin@example.com` 改为你的邮箱
- `codex.example.com` 改为 `codex.talenting.vip`
- `root * /opt/register-bot/frontend/dist` 确认路径正确

### 2.5 启动与验证

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl restart caddy
sudo systemctl status caddy
```

浏览器访问：
- `https://codex.talenting.vip/#/login`

### 2.6 路由说明

示例 Caddyfile 已包含：
- `/api/*` -> `127.0.0.1:8001`
- `/v1/*` -> `127.0.0.1:8001`
- `/ws/*` -> `127.0.0.1:8001`（WebSocket 由 Caddy 自动升级）
- 其余路径走前端静态文件，并回退 `index.html`（SPA）

### 2.7 常见问题

1. 访问 502：
- 检查后端是否监听 `127.0.0.1:8001`
- 检查 Caddyfile 的 `reverse_proxy` 目标端口

2. 访问 404：
- 确认前端已 `npm run build`
- 确认 `root` 指向 `frontend/dist`

3. HTTPS 没生效：
- DNS 未生效或端口 80/443 未放行
- 先 `dig codex.talenting.vip` 验证解析
