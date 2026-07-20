# FitForge 本地 MySQL 容器化 + Volume 持久化沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D11（pydantic-settings 单点配置） + D9（Alembic） + D26（容器化 + Volume 持久化，新增）
> **目的**：面试前复习 + Docker 数据库运维

---

## 1. 为什么用 Docker 容器跑本地 MySQL

| 选项 | 优点 | 缺点 |
|------|------|------|
| 本地装 MySQL | 跟生产部署一致 | 200MB+、配置用户库烦、卸载麻烦 |
| **Docker 容器**（我们选的） | 环境隔离、删容器即清环境、版本切换 1 命令 | 需要装 Docker Desktop（已装）|
| 远程服务器 MySQL | 不用装本地任何东西 | 网络延迟 + 依赖网络 + 风险 |

> **面试话术**：「开发环境我用 Docker 容器跑 MySQL，本地零安装成本、删容器即清环境、生产部署时改 connection string 指向云数据库 RDS 即可。'环境一致 + 快速重建'是容器化的核心价值。」

---

## 2. Docker run 容器持久化的关键参数

```bash
docker run -d \
  --name fitforge-mysql \
  -p 3307:3306 \                          # 主机端口:容器端口（避开 3306 冲突）
  -v mysql_data:/var/lib/mysql \          # 关键：named volume 持久化 MySQL 数据
  -e MYSQL_ROOT_PASSWORD=... \
  -e MYSQL_DATABASE=fitforge \            # 自动建 fitforge 库（但不建用户！）
  -e MYSQL_ROOT_HOST=% \
  --restart unless-stopped \              # Docker Desktop 启动时自动启动容器
  mysql:8.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_unicode_ci \
  --default-authentication-plugin=mysql_native_password
```

### 2.1 `-v mysql_data:/var/lib/mysql` 的关键作用

```
/var/lib/mysql  (容器内 MySQL 数据目录)
        ↓ bind mount
mysql_data     (Docker named volume，存主机上)
```

**持久化效果**：
- `docker stop` + `docker start` → 数据保留（容器内的 inode 没变）
- `docker rm fitforge-mysql` → 容器删了，**mysql_data volume 保留** → 数据安全
- `docker run ... -v mysql_data:/var/lib/mysql ...` → 新容器读 volume 里数据 → 业务恢复

### 2.2 named volume vs bind mount

| 选项 | 路径 | 跨平台 |
|------|------|--------|
| **named volume**（我们选的）| Docker 管理的目录，跨主机路径 | ✅ 跨平台 |
| **bind mount** | 指定主机路径如 `/d/mysql-data` | ⚠️ Windows 路径麻烦 |

**named volume 是默认推荐**——Docker 自动管理，不用担心路径冲突。

> **面试话术**：「我用 Docker named volume（`mysql_data`）持久化 MySQL 数据——这是 Docker 默认推荐的 bind 方式，跨平台不踩路径坑。下次 `docker rm` 容器数据还在，重新 `docker run -v mysql_data:/var/lib/mysql` 数据自动恢复。」

---

## 3. MySQL 8 + caching_sha2_password 密码认证（踩坑点）

### 3.1 报错

```
RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password auth methods
```

### 3.2 原因

- MySQL 8 默认用 `caching_sha2_password` 认证（比 mysql_native_password 安全）
- 但 `caching_sha2_password` 需要 RSA 加密握手，pymysql 需要 `cryptography` 包支持
- **环境变量** `--default-authentication-plugin=mysql_native_password` 只对 root 用户生效
- **CREATE USER 创建的用户**默认用 `caching_sha2_password`（不同步 default plugin）

### 3.3 解决方案（3 选 1）

| 方案 | 命令 | 适用 |
|------|------|------|
| **A. CREATE USER 时显式指定 plugin（推荐）** | `CREATE USER 'fitforge'@'%' IDENTIFIED WITH mysql_native_password BY '...'` | 不用装包，命令行能用 |
| **B. 装 cryptography 包** | `pip install cryptography` | 通用，但 pymysql 包大小增 5MB |
| **C. ALTER USER 改 plugin** | `ALTER USER 'fitforge'@'%' IDENTIFIED WITH mysql_native_password BY '...'` | 已存在用户可补救 |

我们用 **A** + 落地时顺便记录到 .sql 文件 + 加入 commit script。

> **面试话术**：「MySQL 8 默认 caching_sha2_password 认证需要 cryptography 包，我项目里 create user 时显式指定 mysql_native_password——这样 pymysql 不用装额外依赖。这是开发环境部署的'简化决策'：牺牲一点安全性换部署简洁，生产环境应该用 caching_sha2_password + 装 cryptography 包。」

---

## 4. 容器端口冲突：Docker Desktop 占 3306

### 4.1 现象

```bash
$ docker run -p 3306:3306 mysql:8.0
docker: Error response from daemon: failed to set up container networking:
       Bind for 0.0.0.0:3306 failed: port is already allocated
```

### 4.2 根因

- Docker Desktop + WSL2 backend 会用 `com.docker.backend.exe` 占常用端口
- 3306 是常见数据库端口，被 Docker Desktop 抢占
- `netstat` 可看到 `com.docker.backend.exe` 监听 3306

### 4.3 解决方案

- **改端口**：`-p 3307:3306`（主机 3307 → 容器 3306）
- **改 .env 配置**：`DATABASE_URL=mysql+asyncmy://fitforge:...@localhost:3307/fitforge`
- **重启 Docker Desktop**：可能释放占的端口（不保证）

> **面试话术**：「Docker Desktop 在 Windows + WSL2 backend 下会预占常用端口（3306/5432/6379 等），所以我把容器 3306 映射到主机 3307——避开冲突。这是 Docker Desktop 4.x+ 的已知行为，习惯就好。」

---

## 5. 完整运维流程

### 5.1 启动

```bash
# Docker Desktop 启动后（如果停了）
docker run -d --name fitforge-mysql \
  -p 3307:3306 \
  -v mysql_data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD=root_dev_password_2026 \
  -e MYSQL_DATABASE=fitforge \
  -e MYSQL_ROOT_HOST=% \
  --restart unless-stopped \
  mysql:8.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_unicode_ci \
  --default-authentication-plugin=mysql_native_password

# 第一次需要建 fitforge 用户（env var 不建用户）
docker exec -i fitforge-mysql mysql -uroot -proot_dev_password_2026 << 'EOF'
CREATE USER IF NOT EXISTS 'fitforge'@'%' IDENTIFIED WITH mysql_native_password BY 'fitforge_dev_password_2026';
GRANT ALL PRIVILEGES ON fitforge.* TO 'fitforge'@'%';
FLUSH PRIVILEGES;
EOF

# 迁移 schema（如果 data 是空库）
cd project && alembic upgrade head
```

### 5.2 退出 / 临时停

```bash
# 方案 A：保留容器，临时停（数据保留）
docker stop fitforge-mysql

# 方案 B：彻底删容器（数据靠 volume 保留）
docker rm -f fitforge-mysql   # 然后重跑 docker run -v mysql_data:/var/lib/mysql ...

# 方案 C：直接关电脑（容器在 Docker Desktop 后台跑，下次还在）
```

### 5.3 数据备份

```bash
# 导出整个 DB
docker exec fitforge-mysql mysqldump -uroot -p... fitforge > backup.sql

# 用 volume snapshot
docker run --rm -v mysql_data:/from alpine tar czf /backup.tar.gz -C /from .
```

### 5.4 调试命令

```bash
docker ps                              # 看 fitforge-mysql 状态
docker logs --tail 20 fitforge-mysql   # 看 MySQL 启动日志
docker exec -it fitforge-mysql bash    # 进容器调试
docker exec fitforge-mysql mysql -ufitforge -p...  # 进 mysql CLI
```

---

## 6. 面试 Q&A

### Q1：为什么用 named volume 而不是 bind mount？

> "named volume 是 Docker 默认推荐，路径自动管理（Docker 引擎决定），跨平台不踩路径坑。bind mount 写 `/d/path` 在 Windows 下还要处理路径转义，麻烦。生产环境用 named volume，开发环境也可以用。」

### Q2：MySQL 8 caching_sha2_password 报错怎么解？

> "pymysql 缺 cryptography 包支持。我用方案 A：CREATE USER 时显式指定 IDENTIFIED WITH mysql_native_password——不用装包，命令行能用。生产环境应该用 caching_sha2_password + 装 cryptography 包，安全性更高。」

### Q3：Docker Desktop 占 3306 端口怎么处理？

> "改端口映射——`-p 3307:3306` 让容器 3306 映射到主机 3307，避开冲突。Docker Desktop + WSL2 backend 会预占常用端口，这是 Docker Desktop 4.x+ 已知行为。」

### Q4：alembic migration 在 Docker MySQL 上怎么跑？

> "alembic 跟 MySQL 在不同容器（或主机），用 connection string `mysql+pymysql://fitforge:...@localhost:3307/fitforge` 连。alembic init 本地做、autogenerate 对比 Base.metadata（3 个 model）和 DB schema，alembic upgrade head 实际跑 SQL。」

### Q5：如果 volume 删了怎么办？

> "volume 删了数据真的丢，没法恢复。这是 named volume vs bind mount 的权衡——但 bind mount 也可能因主机硬盘故障丢数据。所以生产环境要做定期 mysqldump 备份，开发环境可以接受偶尔重建。」

---

## 7. 踩坑清单

| 坑 | 现象 | 解法 |
|----|------|------|
| 没加 `-v` volume | `docker rm` 后数据全丢 | 加 `-v mysql_data:/var/lib/mysql` |
| 端口 3306 冲突 | `port is already allocated` | 用 `-p 3307:3306` 避开 |
| caching_sha2 报错 | `cryptography package required` | CREATE USER 时指定 `IDENTIFIED WITH mysql_native_password` |
| `--default-authentication-plugin` 只对 root 生效 | CREATE USER 时默认 caching_sha2 | 显式指定 plugin |
| `MYSQL_DATABASE` env var 不建用户 | connect 时报 "user not found" | 手动 CREATE USER + GRANT |
| volume 数据 Docker Desktop 重置会被清 | 数据丢 | 定期 mysqldump 备份 |

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘