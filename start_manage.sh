#!/bin/bash

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANAGE_BACKEND_PID=""
MANAGE_FRONTEND_PID=""

cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭管理服务...${NC}"

    if [ -n "$MANAGE_BACKEND_PID" ] && kill -0 "$MANAGE_BACKEND_PID" 2>/dev/null; then
        kill "$MANAGE_BACKEND_PID" 2>/dev/null
        wait "$MANAGE_BACKEND_PID" 2>/dev/null
        echo -e "${GREEN}✓ 管理后端已关闭${NC}"
    fi

    if [ -n "$MANAGE_FRONTEND_PID" ] && kill -0 "$MANAGE_FRONTEND_PID" 2>/dev/null; then
        kill "$MANAGE_FRONTEND_PID" 2>/dev/null
        wait "$MANAGE_FRONTEND_PID" 2>/dev/null
        echo -e "${GREEN}✓ 管理前端已关闭${NC}"
    fi

    echo -e "${GREEN}所有管理服务已关闭${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  启动管理服务${NC}"
echo -e "${BLUE}========================================${NC}"

# 启动管理后端
echo -e "${YELLOW}启动管理后端 (端口 8686)...${NC}"
cd "$PROJECT_DIR/manage_backend"
uv run python server.py --port 8686 &
MANAGE_BACKEND_PID=$!

# 等待管理后端就绪
echo -e "${YELLOW}等待管理后端就绪...${NC}"
for i in $(seq 1 60); do
    if ! kill -0 "$MANAGE_BACKEND_PID" 2>/dev/null; then
        echo -e "${YELLOW}管理后端进程已退出，启动失败${NC}"
        cleanup
    fi
    if curl -sf "http://localhost:8686/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ 管理后端已就绪${NC}"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo -e "${YELLOW}等待管理后端超时，仍继续启动前端${NC}"
    fi
    sleep 1
done

# 启动管理前端
echo -e "${YELLOW}启动管理前端 (端口 3686)...${NC}"
cd "$PROJECT_DIR/manage_frontend"
npm run dev &
MANAGE_FRONTEND_PID=$!

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  管理服务已就绪${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}管理后端 PID: $MANAGE_BACKEND_PID${NC}"
echo -e "${BLUE}管理前端 PID: $MANAGE_FRONTEND_PID${NC}"
echo -e "${BLUE}管理前端地址: http://localhost:3686${NC}"
echo -e "${BLUE}管理后端地址: http://localhost:8686${NC}"
echo -e "${BLUE}管理 API 文档: http://localhost:8686/docs${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 关闭所有管理服务${NC}"

wait
