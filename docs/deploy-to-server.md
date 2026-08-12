# FitForge 部署到服务器 指南

> **日期**：2026-07-06（周三）
> **关联决策**：D10（uv 包管理）、D11（pydantic-settings）、D26（容器化 + volume）
> **关联资产**：`scripts/deploy_to_server.sh`（自动化脚本）

---

## 1. 部署前 checklist

| 步骤 | 说明 | 完成 |
|------|------|------|
| 服务器是 Ubuntu 22.04 | 其他版本可能 Python 版本不一样 | ✅ 已有 |
| Python 3.10+ 已装 | 3.10 之后类型注解语法更丰富 | ✅ 已有 |
| MySQL 8.0 已装 | fitforge 库已创建 | ✅ 已有 |
| fitforge 用户有 GRANTS | 密码 mysql_native_password | ✅ 已有 |
| SSH 密钥已配 | `ssh fitforge` 直连 | ✅ 已有 |
| 代码已上传到服务器 | scp 或 git pull | ⏳ 待做 |

---

## 2. 5 步部署（最快路径）

### Step 1: 上传代码到服务器

**方式 A：scp（首次）**

```bash
# 在本地 Git Bash 执行（不是服务器）
scp -r D:/My\ Agnet/my_coding_projects/Intelligent_training_management_platform \
    ubuntu@fitforge:~/fitforge
```

**方式 B：git（推荐，已经推到 GitHub 后）**

```bash
# 服务器上
ssh fitforge
git clone https://github.com/lhr6666/FitForge.git ~/fitforge
```

### Step 2: SSH 到服务器

```bash
ssh fitforge
cd ~/fitforge
```

### Step 3: 创建 venv + 装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: 创建 .env（如果上传时没带）

```bash
# 服务器上
cat > .env << 'EOF'
DATABASE_URL=mysql+asyncmy://fitforge:fitforge_dev_password_2026@localhost:3306/fitforge
SYNC_DATABASE_URL=mysql+pymysql://fitforge:fitforge_dev_password_2026@localhost:3306/fitforge
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ALGORITHM=RS256
JWT_EXPIRE_MINUTES=1440
APP_NAME=FitForge
APP_VERSION=0.1.0
DEBUG=false
EOF
```

### Step 5: 跑 deploy 脚本（一键搞定 alembic + uvicorn + 验证）

```bash
# 服务器上
bash scripts/deploy_to_server.sh
```

**脚本自动执行**：
1. ✅ pip install（已装会跳过）
2. ✅ 创建 fitforge 用户（mysql_native_password）
3. ✅ 创建 .env（如果还没有）
4. ✅ alembic upgrade head（建 3 张表）
5. ✅ 启动 uvicorn（后台）
6. ✅ curl 验证 /health、/docs、/auth/register

---

## 3. 验证清单

部署成功后，验证：

```bash
# 1. 健康检查
curl http://localhost:8000/health
# 预期：{"status":"healthy"}

# 2. Swagger UI
# 浏览器打开 http://<服务器IP>:8000/docs
# 预期：看到 "/auth/register" 端点

# 3. 端到端注册
curl -X POST http://localhost:8000/auth/register \
    -H "Content-Type: application/json" \
    -d '{"username":"alice","email":"alice@example.com","password":"Password123"}'
# 预期：201 + {"id":1,"username":"alice",...}

# 4. MySQL 验证
mysql -ufitforge -pfitforge_dev_password_2026 fitforge -e "SHOW TABLES;"
# 预期：alembic_version / body_measurements / user_goals / users
```

---

## 4. 部署后常用命令

```bash
# 查看 uvicorn 日志
tail -f /tmp/uvicorn.log

# 停止 uvicorn
pkill -f "uvicorn main:app"

# 重新部署（代码改了）
git pull
bash scripts/deploy_to_server.sh

# 重启 uvicorn
pkill -f "uvicorn main:app"
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# 看 alembic 状态
alembic current
alembic history

# 跑测试
pytest tests/ -v
```

---

## 5. 踩坑清单

| 坑 | 现象 | 解法 |
|----|------|------|
| ✅ fitforge 库不存在 | `Unknown database 'fitforge'` | `CREATE DATABASE fitforge` |
| ✅ fitforge 用户没权限 | `Access denied for user` | 跑 deploy 脚本 Step 4（创建用户） |
| ✅ caching_sha2 报错 | `cryptography package required` | 用 `IDENTIFIED WITH mysql_native_password` |
| ✅ 3306 端口拒连 | `Connection refused` | MySQL 没启动 / 防火墙拦 |
| ✅ alembic 报没找到 model | `No module named 'models'` | activate venv + cd 项目根目录 |
| ✅ uvicorn 端口占用 | `Address already in use` | `pkill -f uvicorn` |
| ✅ curl 失败 | `Connection refused` | uvicorn 没启动 / 防火墙 |

---

## 6. 与本地开发的工作流对比

| 流程 | 本地（Docker MySQL） | 服务器（System MySQL） |
|------|--------------------|----------------------|
| 启动 MySQL | `docker start fitforge-mysql` | `systemctl start mysql` |
| 启动应用 | `uvicorn main:app --reload` | `nohup uvicorn main:app &` |
| 验证 | `bash tests/smoke.sh` | `curl http://localhost:8000/...` |
| 改代码后 | `--reload` 自动重载 | `git pull` + 手动重启 |
| DB 端口 | 3306:3307（避开 Docker Desktop 占用） | 3306（默认）|

---

## 7. 部署失败时怎么回滚

```bash
# 1. 回滚 alembic
alembic downgrade -1

# 2. 停 uvicorn
pkill -f "uvicorn main:app"

# 3. 完全清理
cd ~ && rm -rf fitforge
```

---

## 8. 安全 checklist（部署完成后）

- [ ] 服务器 SSH 密码登录关闭：`PasswordAuthentication no`（`/etc/ssh/sshd_config`）
- [ ] 防火墙只放行 22 / 80 / 443 端口
- [ ] uvicorn 后面接 nginx（生产用 gunicorn + uvicorn workers）
- [ ] 生产环境 JWT 密钥用 openssl 生成 2048 位 RSA（不要用开发用的 keys/）
- [ ] 日志收集 + 监控告警（生产环境）

---

## 9. 关联文档

- SSH 实战指南：`tech_notes/2026-07-06-ssh-and-cursor-remote-ssh.md`
- Alembic 迁移：`tech_notes/2026-07-06-alembic-migration-workflow.md`
- Docker MySQL 持久化：`tech_notes/2026-07-06-docker-mysql-volume.md`
- 注册端点 spec：`docs/superpowers/specs/2026-07-06-auth-register-design.md`

---

**批准状态**：✅ 用户于 2026-07-06 批准落盘