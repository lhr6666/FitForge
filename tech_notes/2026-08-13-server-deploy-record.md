# FitForge 服务器部署实战记录（2026-08-13 周三）

> **日期**：2026-08-13（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D26（容器化 + Volume 持久化）、D14（SSH 别名 fitforge）、D18（Windows SSH 私钥权限）
> **关联 commit**：`0460a14`（deploy 脚本）+ 服务器实测记录
> **目的**：服务器端到端部署全流程 + 5 个真实踩坑 + 面试话术

---

## 1. 部署目标

把 FitForge 部署到腾讯云 CVM（Ubuntu 22.04，114.132.83.99）：

- ✅ 本地开发完成（17 个 commit）
- ✅ 代码上传到服务器
- ✅ 服务器 Python venv + 依赖
- ✅ MySQL fitforge 库 + fitforge 用户
- ✅ alembic upgrade head 建 3 张表
- ✅ uvicorn 启动 + /health 200
- ✅ 4 个端到端 curl 测试全过

---

## 2. 5 步部署流程（实测）

### Step 1: 上传代码（scp 失败 → tar 替代）

**第一次尝试**（scp + exclude）—— ❌ 失败

```bash
scp -r \
  --exclude=.git \
  --exclude=venv \
  ... . ubuntu@fitforge:~/fitforge
# 报错：scp: unknown option -- --exclude=...
# 原因：scp 不支持 --exclude（只有 rsync 支持）
```

**第二次尝试**（tar 打包 + scp + 解压）—— ✅ 成功

```bash
# 本地
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform"
tar -czf /tmp/fitforge.tar.gz \
  --exclude='.git' --exclude='venv' --exclude='__pycache__' \
  --exclude='.env' --exclude='keys' .

scp /tmp/fitforge.tar.gz ubuntu@fitforge:/tmp/

# 服务器
ssh fitforge
mkdir -p ~/fitforge
tar -xzf /tmp/fitforge.tar.gz -C ~/fitforge/
rm /tmp/fitforge.tar.gz
```

### Step 2: 服务器 .env（**用新密码 lhr076200**）

```bash
cat > ~/fitforge/.env << 'EOF'
DATABASE_URL=mysql+asyncmy://fitforge:lhr076200@localhost:3306/fitforge
SYNC_DATABASE_URL=mysql+pymysql://fitforge:lhr076200@localhost:3306/fitforge
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ALGORITHM=RS256
JWT_EXPIRE_MINUTES=1440
APP_NAME=FitForge
APP_VERSION=0.1.0
DEBUG=false
EOF
```

### Step 3: 改 fitforge 用户 plugin（caching_sha2 → mysql_native_password）

```bash
sudo mysql -e "ALTER USER 'fitforge'@'localhost' \
    IDENTIFIED WITH mysql_native_password BY 'lhr076200'; \
    FLUSH PRIVILEGES;"
```

**为什么需要这步**：MySQL 8 默认 `caching_sha2_password`，pymysql 需 `cryptography` 包才能连。**改 plugin 一行 SQL 解决**。

### Step 4: venv + alembic

```bash
cd ~/fitforge
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

alembic upgrade head
# 输出：Running upgrade -> ec5983897455, create 3 tables
```

### Step 5: uvicorn + 4 个 curl 测试

```bash
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 5

# 验证健康
curl http://localhost:8000/health
# 输出：{"status":"healthy"}

# 4 个端到端测试全过（见 §4）
```

---

## 3. 服务器 4 个端到端测试结果

| Test | 请求 | 响应 | 状态码 |
|------|------|------|--------|
| 1. 正常注册 | `{"username":"serveruser", "email":"server@example.com", "password":"ServerPass1"}` | `{"id":1,"username":"serveruser","nickname":null}` | **201** ✅ |
| 2. username 重复 | `{"username":"serveruser", "email":"server2@example.com", ...}` | `{"detail":"用户名 'serveruser' 已被占用"}` | **409** ✅ |
| 3. 弱密码 | `{"username":"bob", "password":"12345678"}` | `{"detail":[{"msg":"Value error, 密码必须包含字母"...}]}` | **422** ✅ |
| 4. 缺 email | `{"username":"charlie", "password":"Password123"}` | `{"detail":[{"msg":"Field required"...}]}` | **422** ✅ |

**所有路径都对**：业务成功 + 业务异常 + Pydantic 校验。

---

## 4. 5 个真实踩坑 + 修法

### 踩坑 1：scp 不支持 --exclude

**现象**：`scp: unknown option -- --exclude=...`
**原因**：scp 是 OpenSSH 自带，**只有 rsync 支持 --exclude**
**修法**：用 `tar` 打包 → scp → 解压（3 步替代 1 步）

### 踩坑 2：SSH 连接超时断开

**现象**：`Read from remote host 114.132.83.99: Connection reset by peer`
**原因**：空闲超时（中间网络设备 / 腾讯云安全组）
**修法**：`~/.ssh/config` 加 `ServerAliveInterval 60` + `ServerAliveCountMax 3`

### 踩坑 3：.env 没创建成功（SSH 断导致）

**现象**：`cat .env: No such file or directory`
**原因**：`cat > .env << 'EOF'` 写到一半 SSH 断，文件没保存
**修法**：重连后再 cat 一次 + 用 `ls -la .env` 验证文件大小 > 0

### 踩坑 4：MySQL root Access denied

**现象**：`ERROR 1698 (28000): Access denied for user 'root'@'localhost'`
**原因**：Ubuntu 22.04 MySQL 默认 root 用 **auth_socket 插件**（不验证密码）
**修法**：`sudo mysql`（sudo 走 auth_socket 验证 OS 用户，绕过密码验证）

### 踩坑 5：caching_sha2_password 加密握手失败

**现象**：`Access denied for user 'fitforge'@'localhost' (using password: YES)`（用密码登录 fitforge）
**原因**：MySQL 8 默认 `caching_sha2_password`，pymysql 需 `cryptography` 包
**修法**：`ALTER USER ... IDENTIFIED WITH mysql_native_password BY 'lhr076200';`

---

## 5. 完整命令清单（最佳实践）

```bash
# ===== 本地 Git Bash（上传代码）=====
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform"
tar -czf /tmp/fitforge.tar.gz \
  --exclude='.git' --exclude='venv' --exclude='__pycache__' \
  --exclude='.env' --exclude='keys' .
scp /tmp/fitforge.tar.gz ubuntu@fitforge:/tmp/

# ===== 服务器 SSH =====
ssh fitforge
mkdir -p ~/fitforge
tar -xzf /tmp/fitforge.tar.gz -C ~/fitforge/
rm /tmp/fitforge.tar.gz

cd ~/fitforge
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 改 fitforge 用户 plugin（用 sudo mysql）
sudo mysql -e "ALTER USER 'fitforge'@'localhost' \
    IDENTIFIED WITH mysql_native_password BY 'lhr076200'; \
    FLUSH PRIVILEGES;"

# 写 .env
cat > .env << 'EOF'
DATABASE_URL=mysql+asyncmy://fitforge:lhr076200@localhost:3306/fitforge
SYNC_DATABASE_URL=mysql+pymysql://fitforge:lhr076200@localhost:3306/fitforge
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ALGORITHM=RS256
JWT_EXPIRE_MINUTES=1440
APP_NAME=FitForge
APP_VERSION=0.1.0
DEBUG=false
EOF

# alembic 升级
alembic upgrade head

# 启动 uvicorn
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 5

# 验证
curl http://localhost:8000/health
# 预期：{"status":"healthy"}
```

---

## 6. 面试 Q&A

### Q1：部署到服务器踩过最深的坑是什么？

> "MySQL 8 的 caching_sha2_password 认证——pymysql 不支持新协议，需要装 cryptography 或者改 plugin。我选改 plugin，1 行 SQL 解决。这是 90% 部署到 MySQL 8 都会踩的坑。"

### Q2：scp vs rsync vs tar 三种文件传输怎么选？

> "scp 简单但不能 exclude；rsync 支持 exclude 但要装；tar + scp 是最原始的兜底。我项目里 300+ 文件用 tar 打包 1 分钟搞定。生产环境如果用 GitHub → 服务器 git pull 最好。"

### Q3：SSH 连接空闲超时怎么防？

> "客户端配 `ServerAliveInterval 60`（每 60 秒发心跳）+ `ServerAliveCountMax 3`（3 次没响应才断）。腾讯云控制台也可以改'会话超时'配置。两边都配才稳。"

### Q4：Ubuntu 22.04 MySQL root 登不上？

> "MySQL 8 默认用 auth_socket plugin 验证 OS 用户，**不是密码**。要用 `sudo mysql` 登录。fitforge 业务用户可以用密码（IDENTIFIED WITH mysql_native_password）。"

### Q5：服务器部署 vs 本地 Docker MySQL 怎么统一？

> "两个独立环境：本地 Docker MySQL（mysql_native_password，cryptography 都不要装）；服务器 MySQL（改 plugin 到 mysql_native_password）。代码层用 pydantic-settings 读 .env 切换 DATABASE_URL，**不修改业务代码**——这是配置与代码分离的价值。"

---

## 7. 部署完成 checklist

- [x] 代码 tar 打包 + scp 上传
- [x] 服务器 .env 创建（密码 lhr076200，端口 3306）
- [x] fitforge 用户 plugin 改 mysql_native_password
- [x] venv 创建 + 13 个依赖装好
- [x] alembic upgrade head（建 3 张表）
- [x] uvicorn 启动（PID 34525）
- [x] /health 200
- [x] 4 个端到端 curl 测试（201/409/422/422 全过）

---

## 8. 后续优化（生产环境）

- [ ] uvicorn 改 gunicorn + uvicorn workers（多进程）
- [ ] nginx 反向代理 + HTTPS
- [ ] 服务器 SSH 密码登录关闭
- [ ] 日志收集（ELK / Loki）
- [ ] 监控告警（Prometheus + Grafana）
- [ ] CI/CD 自动化部署（GitHub Actions + scp/ssh）

---

**沉淀状态**：✅ 用户于 2026-08-13 批准落盘