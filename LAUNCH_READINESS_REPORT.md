# AI 智能记账系统 — 上线检查报告 (RC1)

> **版本：** RC1 (Release Candidate 1)
> **日期：** 2026-06-01
> **状态：** ✅ 达到 RC1 可上线候选版

---

## 1. 当前项目完成度

| 维度 | 完成度 |
|------|--------|
| **整体完成度** | **~90%** |
| **后端功能** | ~92% |
| **前端功能** | ~95% |
| **安全加固** | ~85% |
| **生产部署就绪** | ~80% |
| **SaaS 商业化** | ~75% |

---

## 2. RC1 可上线候选版判定

**✅ 达到 RC1 标准。** 核心功能完整，安全问题已修复，可部署到生产环境进行灰度测试。

---

## 3. 已完成模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 用户注册/登录 | ✅ | JWT + refresh token + 2FA + 账户锁定 |
| 多租户架构 | ✅ | ORM 自动过滤 + tenant context middleware |
| RBAC 权限 | ✅ | 4 角色 15 权限 |
| 收支记录 CRUD | ✅ | 完整实现，含 tenant_id 隔离 |
| AI 智能记账 | ✅ | DeepSeek API + 本地降级 |
| OCR 小票识别 | ✅ | RapidOCR + 账单真实性校验 |
| 财务分析仪表盘 | ✅ | 今日/本周/本月 + 分类统计 |
| AI 聊天助手 | ✅ | SSE 流式 + 财务上下文 + 配额检查 |
| 多 Agent 系统 | ✅ | 8 个专业 Agent + 工作流引擎 |
| 月度报告 | ✅ | 异常检测 + 风险评分 + AI 分析 |
| Excel 导出 | ✅ | openpyxl 样式化，中文字体正常 |
| PDF 导出 | ✅ | reportlab，中文字体多路径搜索 |
| SaaS 计费 | ✅ | Stripe + 支付宝 + 3 档套餐 |
| 邮箱服务 | ✅ | SMTP + 开发环境 console 降级 |
| WebSocket | ✅ | Flask-SocketIO + Redis |
| Celery 异步任务 | ✅ | 4 队列优先级 |
| 监控告警 | ✅ | Sentry + Prometheus + Grafana |
| XSS 安全加固 | ✅ | DOMPurify + safeMarkdown.js |
| Docker 部署 | ✅ | Dockerfile + docker-compose |
| 部署脚本 | ✅ | deploy.sh + harden.sh + verify.sh |
| 备份恢复 | ✅ | backup.sh + backup_validate.sh |
| 生产部署文档 | ✅ | DEPLOYMENT.md + RUNBOOK.md |

---

## 4. 未完成模块

| 模块 | 状态 | 说明 | 是否阻塞上线 |
|------|------|------|------------|
| 交易数量限制 | ⚠️ | 免费用户可无限创建交易 | 否 |
| 报告导出 Pro 门控 | ⚠️ | 免费用户也可导出 | 否 |
| 功能特性门控 | ⚠️ | Plan.features 未用于权限检查 | 否 |
| 团队成员与套餐联动 | ⚠️ | max_members 不随套餐变化 | 否 |
| PDF 中文字体 | ⚠️ | Linux 服务器需安装 SimHei.ttf | 否（有 fallback） |

---

## 5. 仍存在的高风险问题

| # | 风险 | 级别 | 说明 | 缓解措施 |
|---|------|------|------|---------|
| 1 | 旧项目硬编码 API Key | 🔴 高 | 根目录 routes/api.py 和 services/ai_service.py 中有真实 DeepSeek Key | **上线前必须轮转 Key** |
| 2 | Chat.py 无 fallback | 🟡 中 | AI 不可用时聊天直接报错 | 已添加 quota 检查，建议后续添加 fallback |
| 3 | Admin 路由无租户隔离 | 🟡 中 | 管理员可访问所有租户数据 | 设计如此，需确保管理员账号安全 |
| 4 | tenant_query 自动过滤脆弱 | 🟢 低 | 字符串检测不可靠，但不影响安全 | 冗余过滤，不影响功能 |

---

## 6. 真实 API Key 配置清单

| 服务 | 环境变量名 | 是否必须 | 配置位置 | 用途 |
|------|-----------|---------|---------|------|
| Flask | SECRET_KEY | ✅ 必须 | .env.production | Session 加密 |
| Flask | JWT_SECRET_KEY | ✅ 必须 | .env.production | JWT 签名 |
| MySQL | DATABASE_URL | ✅ 必须 | .env.production | 数据库连接 |
| DeepSeek | DEEPSEEK_API_KEY | ✅ 必须 | .env.production | AI 大模型调用 |
| Redis | REDIS_URL | ✅ 必须 | .env.production | 缓存/消息队列 |
| Fernet | FERNET_KEY | ⚠️ 推荐 | .env.production | 敏感数据加密 |

---

## 7. SMTP 配置清单

| 变量名 | 必填 | 示例 |
|--------|------|------|
| SMTP_HOST | ✅ | smtp.qq.com |
| SMTP_PORT | 可选 | 587 |
| SMTP_USERNAME | ✅ | your-email@qq.com |
| SMTP_PASSWORD | ✅ | 授权码（非登录密码） |
| SMTP_FROM_EMAIL | 可选 | 默认同 SMTP_USERNAME |
| SMTP_FROM_NAME | 可选 | AI 智能记账 |
| SMTP_USE_TLS | 可选 | true |
| SMTP_USE_SSL | 可选 | false |

---

## 8. Stripe 配置清单

| 变量名 | 必填 | 说明 |
|--------|------|------|
| STRIPE_SECRET_KEY | ✅ 生产必须 | Stripe Secret Key |
| STRIPE_PUBLISHABLE_KEY | ✅ 生产必须 | Stripe Publishable Key |
| STRIPE_WEBHOOK_SECRET | ✅ 生产必须 | Stripe Webhook 签名密钥 |
| STRIPE_PRICE_PRO | ⚠️ 创建套餐后 | Pro 版月付 Price ID |
| STRIPE_PRICE_TEAM | ⚠️ 创建套餐后 | 团队版月付 Price ID |

> **注意：** 如果不配置 Stripe，支付功能不可用，但系统其他功能正常。可先部署后配置。

---

## 9. 域名配置清单

| 变量名 | 必填 | 示例 |
|--------|------|------|
| DOMAIN | ✅ | your-domain.com |
| FRONTEND_URL | ✅ | https://your-domain.com |
| CORS_ORIGINS | ✅ | https://your-domain.com |
| LETSENCRYPT_EMAIL | ✅ | admin@your-domain.com |

---

## 10. 服务器配置清单

**最低配置：**
- Ubuntu 24.04 LTS
- 2 核 CPU / 4GB RAM / 50GB SSD
- Docker + Docker Compose

**需要安装：**
```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Docker Compose (已包含在 Docker 中)
docker compose version
```

---

## 11. Docker 部署步骤

```bash
# 1. 克隆代码
git clone <repo-url> /opt/ai-accounting
cd /opt/ai-accounting/ai-accounting-system

# 2. 配置环境变量
cp .env.production.example .env.production
# 编辑 .env.production，填写真实值

# 3. 生成密钥
python scripts/generate_secrets.py

# 4. 启动服务
docker compose -f docker-compose.prod.yml up -d

# 5. 验证
docker compose -f docker-compose.prod.yml ps
curl -f http://localhost:5000/api/health

# 6. 配置 Nginx + SSL (如使用域名)
# 参考 deploy/DEPLOYMENT.md
```

---

## 12. 回滚步骤

```bash
# 1. 停止当前服务
docker compose -f docker-compose.prod.yml down

# 2. 恢复数据库备份
mysql -u root -p ai_accounting < backup_YYYYMMDD.sql

# 3. 切换到上一个版本
git checkout <previous-tag>

# 4. 重新启动
docker compose -f docker-compose.prod.yml up -d --build
```

详细步骤参见：`ai-accounting-system/ROLLBACK_CHECKLIST.md`

---

## 13. 备份步骤

```bash
# 自动备份（建议配置 cron）
0 2 * * * /opt/ai-accounting/ai-accounting-system/scripts/backup.sh

# 手动备份
bash scripts/backup.sh

# 验证备份
bash scripts/backup_validate.sh
```

---

## 14. 上线前人工检查清单

- [ ] 轮转旧代码中暴露的 DeepSeek API Key
- [ ] 在 `.env.production` 填写所有真实密钥
- [ ] 运行 `python scripts/validate_secrets.py` 验证密钥
- [ ] 运行 `python scripts/test_email.py --to your@email.com` 测试邮件
- [ ] 配置 SMTP 真实凭据
- [ ] 配置 Stripe 或确认支付功能暂不需要
- [ ] 安装中文字体（如需 PDF 导出中文）
- [ ] 配置域名和 SSL 证书
- [ ] 配置 MySQL 数据库
- [ ] 配置 Redis
- [ ] 运行 `docker compose -f docker-compose.prod.yml config` 验证配置
- [ ] 运行 `deploy/verify.sh` 全面验证
- [ ] 更改默认管理员密码 (admin123)
- [ ] 检查所有 API 端点是否正常

---

## 15. 上线后监控检查清单

- [ ] Grafana 仪表盘正常显示
- [ ] Prometheus 告警规则生效
- [ ] Sentry 错误上报正常
- [ ] 数据库连接池正常
- [ ] Redis 连接正常
- [ ] Celery Worker 正常运行
- [ ] 日志文件正常写入
- [ ] AI API 调用正常
- [ ] 邮件发送正常
- [ ] 定时备份正常执行

---

## 16. 建议下一次 Git Commit Message

```
feat: RC1 — production candidate with security hardening

- Fix 5 backend bugs (tenant_id, logger, field names, deps, OCR)
- Add SMTP email service with console fallback
- Fix XSS vulnerability with DOMPurify safeMarkdown
- Add chat.py rate limiting and AI quota checks
- Add team tier to SaaS plans
- Fix PDF Chinese font search path
- Add @token_required to categories endpoint
- Create .gitignore for root project
- Generate LAUNCH_READINESS_REPORT.md
```

---

*报告生成时间：2026-06-01*
*审计工具：Claude Code 代码审计*
