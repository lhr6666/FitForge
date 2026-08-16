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
 
#本地再删除掉原本的临时文件
rm /tmp/fitforge.tar.gz
    
```

### Step 2: 服务器 .env（**用新密码 lhr076200**）

服务器执行：`cat > ~/fitforge/.env << 'EOF'` → 输入多行内容 → `EOF`结束。

- `cat > 文件`：覆盖写入文件；`<< 'EOF'`：以`EOF`为结束标记的多行输入。  
运行原理：shell将`EOF`之间的内容作为标准输入传递给`cat`，`cat`写入指定文件。

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

因为MySQL 8 默认用 `caching_sha2_password` 这个新认证方式，但我们的 Python 库（`pymysql` 或 `asyncmy`）不认识它，导致连接失败。

所以，我们需要用ALTER USER这个sql语句把 `fitforge` 用户的认证方式从 `caching_sha2_password` **改成** `mysql_native_password`。而要执行这个语句需要以 MySQL `root` 用户的身份去执行 `ALTER USER` 命令，去修改 `fitforge` 用户的认证方式。为了使用root身份要在服务器本地，并且用 `sudo` 命令（比如 `sudo mysql`）来登录，`auth_socket` 就认为你是可信的，所以我们用 `sudo` 登录时，MySQL 会自动放行，不需要我们输入 `root` 的密码就可以登陆。

而我的fit forge应用是python写的，而 MySQL 是一个用 C++ 写的独立程序。Python 和 MySQL 之间“语言不通”，无法直接对话。fitforge的数据存到了MySQL里面要读取必须通过中间翻译官（把 Python 的请求翻译成 MySQL 能听懂的语言，再把 MySQL 的回应翻译回 Python 能理解的内容）`pymysql` **或**`asyncmy。而无论哪个`在和 MySQL 对话的过程中，需要用到密码 `lhr076200` 来证明身份。

- `pymysql`：这是一个“同步”的翻译官。它的工作方式是“你问一句，我等它回答，然后再问下一句”。适合处理简单的、顺序执行的任务。
- eg：**数据库迁移工具** `alembic`：它可能用的是 `pymysql`（同步方式）来执行 `CREATE TABLE` 等操作。因为它通常是按顺序执行，不需要异步。

- `asyncmy`：这是一个“异步”的翻译官。它的工作方式是“我把问题丢过去，不等回答，继续做别的事，等答案回来我再处理”。适合处理高并发的、需要同时处理很多请求的任务（比如你的 Web 服务器）。
- eg：**你的 FastAPI 应用**：它用的是 `asyncmy`（异步方式）来处理用户的 HTTP 请求。因为 Web 服务器需要同时处理成百上千个请求，异步方式效率更高。

  


```bash
sudo mysql -e "ALTER USER 'fitforge'@'localhost' \
    IDENTIFIED WITH mysql_native_password BY 'lhr076200'; \
    FLUSH PRIVILEGES;"#FLUSH PRIVILEGES是MySQL SQL语句，用于刷新权限表，使权限修改立即生效。诞生于MySQL早期，核#心作用是重新加载权限缓存，适用场景为修改用户权限后需立即生效。
```

**为什么需要这步**：MySQL 8 默认 `caching_sha2_password`，pymysql 需 `cryptography` 包才能连。**改 plugin 一行 SQL 解决**。

### Step 4: venv + alembic（虚拟环境配置+完成数据迁移）

当你执行了 `python3 -m venv venv` 创建虚拟环境，然后 `source venv/bin/activate` 激活它之后，你接下来用 `pip install` 安装的**所有依赖，都会被安装到这个** `venv` **虚拟环境里**，而不是你服务器上全局的 Python 环境。

这就像你给 FitForge 项目建立了一个**专属的、隔离的“小厨房”**。在这个小厨房里，你安装的任何“调料”（比如 FastAPI、SQLAlchemy）都只属于 FitForge，不会跑到外面去影响其他项目。

所以，你用 `pip install -r requirements.txt` 安装的依赖，都精准地落在了 `~/fitforge/venv/` 这个目录下

```bash
cd ~/fitforge
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

#alembic 就是一个“建筑队”，它根据你的代码蓝图，把数据库的“房子”（表结构）从旧样子改造成新样子。
alembic upgrade head
# 输出：Running upgrade -> ec5983897455, create 3 tables
```

### Step 5: uvicorn + 4 个 curl 测试

```bash
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 5

# 验证健康
#。curl可发送GET请求，获取响应状态码和内容，验证服务健康。若不用curl，用浏览器访问无法显示详细响应（如状态码、响应体），且无法自动化测试。
curl http://localhost:8000/health
# 输出：{"status":"healthy"}

# 4 个端到端测试全过（见 §4）
```

---

## 3. 服务器 4 个端到端测试结果


| Test           | 请求                                                                                  | 响应                                                 | 状态码       |
| -------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------- | --------- |
| 1. 正常注册        | `{"username":"serveruser", "email":"server@example.com", "password":"ServerPass1"}` | `{"id":1,"username":"serveruser","nickname":null}` | **201** ✅ |
| 2. username 重复 | `{"username":"serveruser", "email":"server2@example.com", ...}`                     | `{"detail":"用户名 'serveruser' 已被占用"}`               | **409** ✅ |
| 3. 弱密码         | `{"username":"bob", "password":"12345678"}`                                         | `{"detail":[{"msg":"Value error, 密码必须包含字母"...}]}`  | **422** ✅ |
| 4. 缺 email     | `{"username":"charlie", "password":"Password123"}`                                  | `{"detail":[{"msg":"Field required"...}]}`         | **422** ✅ |


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