#!/bin/bash
# =============================================================================
# AI Accounting System — 一键部署脚本
# =============================================================================
# 用法: bash deploy.sh
# 前提: 项目文件已上传到 /opt/ledgerai/ai-accounting-system/
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_DIR="/opt/ledgerai/ai-accounting-system"
COMPOSE_FILE="docker-compose.prod.yml"

echo ""
echo "=========================================="
echo "  AI 智能记账系统 — 生产部署"
echo "=========================================="
echo ""

# ---- Step 1: 检查项目目录 ----
echo -e "${YELLOW}[1/7] 检查项目目录...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}错误: 项目目录不存在: $PROJECT_DIR${NC}"
    echo "请先上传项目文件到 /opt/ledgerai/"
    exit 1
fi
cd "$PROJECT_DIR"
echo -e "${GREEN}✓ 项目目录就绪: $PROJECT_DIR${NC}"

# ---- Step 2: 检查 .env.production ----
echo ""
echo -e "${YELLOW}[2/7] 检查 .env.production...${NC}"
if [ ! -f ".env.production" ]; then
    echo -e "${RED}错误: .env.production 不存在${NC}"
    echo "请先创建 .env.production 并填入真实值"
    exit 1
fi

# 检查关键字段是否为空
EMPTY_FIELDS=""
grep -q "^DEEPSEEK_API_KEY=$" .env.production && EMPTY_FIELDS="$EMPTY_FIELDS DEEPSEEK_API_KEY"
grep -q "^ADMIN_PASSWORD=$" .env.production && EMPTY_FIELDS="$EMPTY_FIELDS ADMIN_PASSWORD"
grep -q "^SECRET_KEY=$" .env.production && EMPTY_FIELDS="$EMPTY_FIELDS SECRET_KEY"

if [ -n "$EMPTY_FIELDS" ]; then
    echo -e "${RED}警告: 以下字段为空:$EMPTY_FIELDS${NC}"
    echo -e "${YELLOW}请编辑 .env.production 填入真实值后重新运行${NC}"
    echo "  nano $PROJECT_DIR/.env.production"
    exit 1
fi
echo -e "${GREEN}✓ .env.production 已配置${NC}"

# ---- Step 3: 停止旧容器 ----
echo ""
echo -e "${YELLOW}[3/7] 停止旧容器...${NC}"
if docker compose -f $COMPOSE_FILE ps -q 2>/dev/null | grep -q .; then
    docker compose -f $COMPOSE_FILE down
    echo -e "${GREEN}✓ 旧容器已停止${NC}"
else
    echo -e "${GREEN}✓ 无运行中的旧容器${NC}"
fi

# ---- Step 4: 构建镜像 ----
echo ""
echo -e "${YELLOW}[4/7] 构建 Docker 镜像（首次约 5-10 分钟）...${NC}"
docker compose -f $COMPOSE_FILE build --no-cache
echo -e "${GREEN}✓ 镜像构建完成${NC}"

# ---- Step 5: 启动服务 ----
echo ""
echo -e "${YELLOW}[5/7] 启动所有服务...${NC}"
docker compose -f $COMPOSE_FILE up -d
echo -e "${GREEN}✓ 服务已启动${NC}"

# ---- Step 6: 等待健康检查 ----
echo ""
echo -e "${YELLOW}[6/7] 等待服务就绪（约 60 秒）...${NC}"
for i in $(seq 1 30); do
    if curl -sf http://localhost/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端服务就绪${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}警告: 后端服务启动超时，请检查日志${NC}"
        echo "  docker compose -f $COMPOSE_FILE logs backend"
    fi
    sleep 2
    printf "."
done

# ---- Step 7: 输出状态 ----
echo ""
echo ""
echo -e "${YELLOW}[7/7] 部署状态${NC}"
echo "=========================================="
echo ""
echo "--- 容器状态 ---"
docker compose -f $COMPOSE_FILE ps
echo ""

echo "--- 健康检查 ---"
HEALTH=$(curl -sf http://localhost/api/health 2>/dev/null || echo '{"status":"unreachable"}')
echo "  /api/health: $HEALTH"
echo ""

echo "--- 访问地址 ---"
SERVER_IP=$(curl -sf http://checkip.amazonaws.com 2>/dev/null || hostname -I | awk '{print $1}')
echo "  前端: http://$SERVER_IP"
echo "  API:  http://$SERVER_IP/api/health"
echo ""

echo "=========================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "=========================================="
echo ""
echo "常用命令:"
echo "  查看日志: docker compose -f $COMPOSE_FILE logs -f"
echo "  重启服务: docker compose -f $COMPOSE_FILE restart"
echo "  停止服务: docker compose -f $COMPOSE_FILE down"
echo "  进入后端: docker compose -f $COMPOSE_FILE exec backend bash"
echo ""
