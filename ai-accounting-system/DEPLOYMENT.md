# AI Accounting System — 生产部署指南

## 服务器信息

| 项目 | 值 |
|------|-----|
| 系统 | Ubuntu 22.04 |
| 公网 IP | 8.210.26.225 |
| 域名 | ledgerai.store / www.ledgerai.store |
| Docker | 已安装 |
| Docker Compose | 已安装 |

---

## 一、部署前准备

### 1.1 本地：生成密钥

在本地执行以下命令生成所有需要的密钥：

```bash
# 生成 SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# 生成 JWT_SECRET_KEY（必须与 SECRET_KEY 不同）
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"

# 生成 FERNET_KEY
python -c "from cryptography.fernet import Fernet; print('FERNET_KEY=' + Fernet.generate_key().decode())"

# 生成 REDIS_PASSWORD
python -c "import secrets,string; print('REDIS_PASSWORD=' + ''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))"

# 生成 MYSQL_ROOT_PASSWORD
python -c "import secrets,string; print('MYSQL_ROOT_PASSWORD=' + ''.join(secrets.choice(string.ascii_letters+string.digits+'!@#') for _ in range(24)))"

# 生成 MYSQL_PASSWORD
python -c "import secrets,string; print('MYSQL_PASSWORD=' + ''.join(secrets.choice(string.ascii_letters+string.digits+'!@#') for _ in range(24)))"

# 生成 ADMIN_PASSWORD
python -c "import secrets,string; print('ADMIN_PASSWORD=' + ''.join(secrets.choice(string.ascii_letters+string.digits+'!@#') for _ in range(16)))"

# 生成 GRAFANA_PASSWORD
python -c "import secrets,string; print('GRAFANA_PASSWORD=' + ''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(16)))"

# 生成 METRICS_AUTH_TOKEN
python -c "import secrets; print('METRICS_AUTH_TOKEN=' + secrets.token_hex(32))"

# 生成 REQUEST_SIGNING_SECRET
python -c "import secrets; print('REQUEST_SIGNING_SECRET=' + secrets.token_hex(32))"

# 生成 MYSQL_EXPORTER_PASSWORD
python -c "import secrets,string; print('MYSQL_EXPORTER_PASSWORD=' + ''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))"
```

### 1.2 本地：创建 .env.production

```bash
cd ai-accounting-system
cp .env.production.example .env.production
# 用上面生成的密钥填入 .env.production
# 重点填写：
#   - 所有密钥（上面生成的）
#   - DEEPSEEK_API_KEY（你的 DeepSeek API Key）
#   - CORS_ORIGINS=https://ledgerai.store,https://www.ledgerai.store
#   - FRONTEND_URL=https://ledgerai.store
#   - ADMIN_PASSWORD（上面生成的）
```

### 1.3 本地：提交代码

```bash
git add -A
git commit -m "feat: production deployment configs"
git push origin main
```

---

## 二、服务器部署

### 2.1 SSH 登录服务器

```bash
ssh root@8.210.26.225
```

### 2.2 安装 Docker（如果未安装）

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose 插件
apt install -y docker-compose-plugin

# 验证
docker --version
docker compose version
```

### 2.3 克隆代码

```bash
cd /opt
git clone https://github.com/JasonSmith968/ai-bill-system.git
cd ai-bill-system/ai-accounting-system
```

### 2.4 配置 .env.production

```bash
cp .env.production.example .env.production
nano .env.production
```

填入所有密钥和配置。关键配置：

```env
# Flask
FLASK_ENV=production
SECRET_KEY=<你生成的 SECRET_KEY>
JWT_SECRET_KEY=<你生成的 JWT_SECRET_KEY>
FERNET_KEY=<你生成的 FERNET_KEY>

# MySQL
MYSQL_ROOT_PASSWORD=<你生成的 MYSQL_ROOT_PASSWORD>
MYSQL_DATABASE=ai_accounting
MYSQL_USER=ai_user
MYSQL_PASSWORD=<你生成的 MYSQL_PASSWORD>
DATABASE_URL=mysql+pymysql://ai_user:<MYSQL_PASSWORD>@mysql:3306/ai_accounting?charset=utf8mb4

# Redis
REDIS_PASSWORD=<你生成的 REDIS_PASSWORD>
REDIS_URL=redis://:<REDIS_PASSWORD>@redis:6379/0

# AI
DEEPSEEK_API_KEY=<你的 DeepSeek API Key>

# Domain
DOMAIN=ledgerai.store
CORS_ORIGINS=https://ledgerai.store,https://www.ledgerai.store
FRONTEND_URL=https://ledgerai.store
BACKEND_URL=https://ledgerai.store

# Admin
ADMIN_PASSWORD=<你生成的 ADMIN_PASSWORD>

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=<你生成的 GRAFANA_PASSWORD>
```

### 2.5 创建 SSL 目录

```bash
mkdir -p nginx/ssl
```

### 2.6 构建并启动

```bash
# 构建所有镜像
docker compose -f docker-compose.prod.yml build

# 启动所有服务
docker compose -f docker-compose.prod.yml up -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f
```

### 2.7 验证服务

```bash
# 检查所有容器状态
docker compose -f docker-compose.prod.yml ps

# 测试后端健康检查
curl http://localhost/api/health

# 测试前端
curl -I http://localhost/
```

---

## 三、域名和 SSL 配置

### 3.1 DNS 解析配置

在域名服务商（如阿里云、Cloudflare）添加 A 记录：

| 主机记录 | 类型 | 记录值 |
|----------|------|--------|
| @ | A | 8.210.26.225 |
| www | A | 8.210.26.225 |

### 3.2 申请 SSL 证书（Certbot）

DNS 解析生效后（通常几分钟到几小时）：

```bash
# 申请证书
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d ledgerai.store -d www.ledgerai.store \
  --email your-email@example.com --agree-tos --no-eff-email

# 复制证书到 nginx ssl 目录
cp /etc/letsencrypt/live/ledgerai.store/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/ledgerai.store/privkey.pem nginx/ssl/
```

### 3.3 启用 HTTPS

编辑 `nginx/production.conf`：

1. 注释掉 HTTP server 块中的直接响应
2. 添加 HTTP → HTTPS 重定向
3. 取消注释 HTTPS server 块

```bash
# 重载 nginx
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### 3.4 自动续期

```bash
# 添加 crontab
crontab -e

# 添加以下行（每天凌晨 2 点尝试续期）
0 2 * * * cd /opt/ai-bill-system/ai-accounting-system && docker compose -f docker-compose.prod.yml run --rm certbot renew --quiet && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## 四、常用运维命令

### 4.1 服务管理

```bash
# 查看所有服务状态
docker compose -f docker-compose.prod.yml ps

# 查看实时日志
docker compose -f docker-compose.prod.yml logs -f

# 查看某个服务日志
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx

# 重启所有服务
docker compose -f docker-compose.prod.yml restart

# 重启单个服务
docker compose -f docker-compose.prod.yml restart backend

# 停止所有服务
docker compose -f docker-compose.prod.yml down

# 停止并删除数据卷（危险！会丢失数据）
docker compose -f docker-compose.prod.yml down -v
```

### 4.2 更新部署

```bash
cd /opt/ai-bill-system

# 拉取最新代码
git pull origin main

# 重新构建并部署
cd ai-accounting-system
docker compose -f docker-compose.prod.yml up -d --build

# 清理旧镜像
docker image prune -f
```

### 4.3 数据库备份

```bash
# 备份 MySQL
docker compose -f docker-compose.prod.yml exec mysql mysqldump \
  -u root -p"${MYSQL_ROOT_PASSWORD}" ai_accounting > backup_$(date +%Y%m%d).sql

# 恢复 MySQL
docker compose -f docker-compose.prod.yml exec -T mysql mysql \
  -u root -p"${MYSQL_ROOT_PASSWORD}" ai_accounting < backup_20260602.sql
```

### 4.4 进入容器调试

```bash
# 进入后端容器
docker compose -f docker-compose.prod.yml exec backend bash

# 进入 MySQL
docker compose -f docker-compose.prod.yml exec mysql mysql -u ai_user -p ai_accounting

# 进入 Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli -a "${REDIS_PASSWORD}"
```

---

## 五、监控（可选）

如需 Prometheus + Grafana 监控栈，使用 `docker-compose.security.yml` 叠加：

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.security.yml up -d
```

Grafana 访问：`http://8.210.26.225:3000`（仅限服务器本地或 SSH 隧道）

```bash
# SSH 隧道访问 Grafana
ssh -L 3000:localhost:3000 root@8.210.26.225
```

---

## 六、安全检查清单

- [ ] `.env.production` 已创建且包含强密钥
- [ ] `.env.production` 未提交到 Git
- [ ] `ADMIN_PASSWORD` 已修改（非默认值）
- [ ] `DEEPSEEK_API_KEY` 已填入
- [ ] `CORS_ORIGINS` 仅包含正式域名
- [ ] `FLASK_ENV=production`
- [ ] `DEBUG` 未开启
- [ ] MySQL 端口 3306 未对外暴露
- [ ] Redis 端口 6379 未对外暴露
- [ ] SSL 证书已配置
- [ ] 防火墙仅开放 80/443 端口

### 防火墙配置（Ubuntu）

```bash
# 使用 ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## 七、故障排查

### 后端无法启动

```bash
# 查看后端日志
docker compose -f docker-compose.prod.yml logs backend

# 常见原因：
# 1. DATABASE_URL 连接失败 → 检查 MySQL 是否就绪
# 2. SECRET_KEY 未设置 → 检查 .env.production
# 3. 端口冲突 → 检查 5000 端口是否被占用
```

### 前端无法访问

```bash
# 检查 nginx 日志
docker compose -f docker-compose.prod.yml logs nginx

# 检查前端容器
docker compose -f docker-compose.prod.yml ps frontend
```

### AI 功能不工作

```bash
# 检查 DEEPSEEK_API_KEY 是否正确设置
docker compose -f docker-compose.prod.yml exec backend env | grep DEEPSEEK

# 检查后端日志中的 AI 相关错误
docker compose -f docker-compose.prod.yml logs backend | grep -i "deepseek\|llm\|api_key"
```

---

## 八、架构说明

```
                    ┌─────────────────────────────────────────┐
                    │              Internet                    │
                    └─────────────────┬───────────────────────┘
                                      │
                              ┌───────▼───────┐
                              │   Nginx:80    │  (ai-nginx)
                              │  反向代理      │
                              └───────┬───────┘
                       ┌──────────────┼──────────────┐
                       │              │              │
               ┌───────▼───────┐     │     ┌────────▼────────┐
               │  Frontend:80  │     │     │   Backend:5000  │
               │  (Vue SPA)    │     │     │   (Flask API)   │
               └───────────────┘     │     └────────┬────────┘
                                     │              │
                              ┌──────▼──────┐  ┌────▼─────┐
                              │  MySQL:3306 │  │Redis:6379│
                              └─────────────┘  └──────────┘
```

**容器网络：**
- `frontend-net`: nginx ↔ frontend, nginx ↔ backend
- `backend-net` (internal): backend ↔ mysql, backend ↔ redis, celery ↔ mysql, celery ↔ redis
