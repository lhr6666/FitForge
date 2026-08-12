#!/bin/bash
# FitForge 一键部署脚本 - 在服务器上跑
# Usage: bash scripts/deploy_to_server.sh

set -e

# ============ 配置 ============
PROJECT_DIR="$HOME/fitforge"
VENV_DIR="$PROJECT_DIR/venv"
DB_NAME="fitforge"
DB_USER="fitforge"
DB_PASSWORD="fitforge_dev_password_2026"
DB_HOST="localhost"
DB_PORT="3306"

echo "=== FitForge 部署脚本 ==="
echo "Project: $PROJECT_DIR"
echo "Database: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""

# ============ Step 1: 项目目录 ============
cd "$PROJECT_DIR" || { echo "ERROR: $PROJECT_DIR 不存在，请先上传代码"; exit 1; }

# ============ Step 2: 激活 venv ============
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: venv 不存在，请先 python3 -m venv venv"
    exit 1
fi
source "$VENV_DIR/bin/activate"

# ============ Step 3: 安装依赖 ============
echo ""
echo "=== Step 3: pip install -r requirements.txt ==="
pip install -r requirements.txt

# ============ Step 4: 确保 fitforge 用户用 mysql_native_password ============
echo ""
echo "=== Step 4: 确保 fitforge 用户用 mysql_native_password ==="
docker_exec_mysql() {
    if command -v docker >/dev/null 2>&1 && docker ps | grep -q mysql; then
        # Docker 跑 MySQL
        docker exec -i fitforge-mysql mysql -uroot -e "$1"
    else
        # 系统 MySQL
        mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "$1"
    fi
}

# 假设用户已经有了 server 自己的 MySQL 容器 / 系统 MySQL
# 注意：这里是 dev 密码，生产要换
docker_exec_mysql "
CREATE USER IF NOT EXISTS '$DB_USER'@'$DB_HOST' IDENTIFIED WITH mysql_native_password BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'$DB_HOST';
FLUSH PRIVILEGES;
" || echo "WARN: 创建用户失败（可能已经是期望状态）"

# ============ Step 5: 配 .env（如果还没有） ============
if [ ! -f .env ]; then
    echo ""
    echo "=== Step 5: 创建 .env ==="
    cat > .env << EOF
DATABASE_URL=mysql+asyncmy://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME
SYNC_DATABASE_URL=mysql+pymysql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ALGORITHM=RS256
JWT_EXPIRE_MINUTES=1440
APP_NAME=FitForge
APP_VERSION=0.1.0
DEBUG=false
EOF
    echo ".env 已创建"
fi

# ============ Step 6: alembic upgrade head ============
echo ""
echo "=== Step 6: alembic upgrade head ==="
alembic upgrade head

# ============ Step 7: 启动 uvicorn（可选） ============
echo ""
echo "=== Step 7: 启动 uvicorn（后台）==="
if pgrep -f "uvicorn main:app" >/dev/null; then
    echo "uvicorn 已在跑，先 stop"
    pkill -f "uvicorn main:app" || true
    sleep 2
fi
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
echo "uvicorn PID: $!"
sleep 5

# ============ Step 8: 验证 ============
echo ""
echo "=== Step 8: 验证 ==="
if curl -s http://localhost:8000/health >/dev/null; then
    echo "✓ /health OK"
else
    echo "✗ /health 失败，查看 /tmp/uvicorn.log"
    tail -20 /tmp/uvicorn.log
    exit 1
fi

if curl -s http://localhost:8000/docs -o /dev/null && [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/docs)" = "200" ]; then
    echo "✓ /docs OK (Swagger UI)"
else
    echo "✗ /docs 失败"
    exit 1
fi

# ============ Step 9: 端到端测试 /auth/register ============
echo ""
echo "=== Step 9: 端到端测试 /auth/register ==="
# Test 1: 成功注册
RESP=$(curl -s -X POST http://localhost:8000/auth/register \
    -H "Content-Type: application/json" \
    -d '{"username":"serveruser","email":"server@example.com","password":"ServerPass1"}' \
    -w "\nHTTP_CODE:%{http_code}")
echo "Test 1 (register success): $RESP"

# Test 2: 重复 username
RESP=$(curl -s -X POST http://localhost:8000/auth/register \
    -H "Content-Type: application/json" \
    -d '{"username":"serveruser","email":"server2@example.com","password":"ServerPass1"}' \
    -w "\nHTTP_CODE:%{http_code}")
echo "Test 2 (duplicate username): $RESP"

# Test 3: 弱密码
RESP=$(curl -s -X POST http://localhost:8000/auth/register \
    -H "Content-Type: application/json" \
    -d '{"username":"serverbob","email":"bob@example.com","password":"12345678"}' \
    -w "\nHTTP_CODE:%{http_code}")
echo "Test 3 (weak password): $RESP"

echo ""
echo "=== 部署完成 ==="
echo "uvicorn 跑在 http://0.0.0.0:8000"
echo "查看日志: tail -f /tmp/uvicorn.log"
echo "停止: pkill -f 'uvicorn main:app'"
