# Error: pymysql + MySQL 8 caching_sha2_password 加密握手失败

> **日期**：2026-08-13（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联 commit**：`fff8b3d`（alembic migration）→ 服务器端验证时发现
> **关联决策**：D26（本地 Docker + 服务器双部署）
> **状态**：✅ 已解决

---

## 1. 报错信息

服务器上跑 `alembic upgrade head` 时：

```
sqlalchemy.exc.OperationalError: (asyncmy.errors.OperationalError)
(2003, "Can't connect to MySQL server on 'localhost'")

# 或 pymysql 场景：
RuntimeError: 'cryptography' package is required for sha256_password
                or caching_sha2_password auth methods
```

## 2. 根因


| 层级               | 详情                                            |
| ---------------- | --------------------------------------------- |
| **MySQL 8 默认认证** | `caching_sha2_password`（MySQL 5.7+ 默认）        |
| **认证机制**         | RSA 加密握手（密码本身不传输，用公钥加密）                       |
| **Python 客户端支持** | pymysql 内置 SHA1 哈希，**不内置 RSA**                |
| **需要**           | `cryptography` Python 包（PyMySQL 通过它调 OpenSSL） |


**关键**：MySQL 8 用新认证协议 → pymysql 需要 cryptography 才能连。

## 3. 解决方案（3 选 1）

### 方案 A：装 cryptography 包（推荐，最快）

```bash
pip install cryptography
```

- ✅ 1 行命令
- ✅ 不动 MySQL 配置
- ✅ pymysql/asyncmy 都受益
- ⚠️ cryptography 包多 5MB

### 方案 B：改 MySQL 用户 plugin（也快）

```sql
ALTER USER 'fitforge'@'localhost'
    IDENTIFIED WITH mysql_native_password BY 'lhr076200';
FLUSH PRIVILEGES;
```

- ✅ 不装包
- ✅ pymysql 直接连
- ⚠️ 改 MySQL 配置（生产环境慎改）
- ⚠️ 跟 .env 密码耦合（要保证两处一致）

### 方案 C：MySQL 容器启动加 `--default-authentication-plugin`（预防性）

```bash
docker run ... mysql:8.0 \
    --default-authentication-plugin=mysql_native_password
```

- ✅ 容器内**新用户**默认用老认证
- ⚠️ 已存在的用户不会变（仍用 caching_sha2）

## 4. FitForge 实际方案

我们用了**方案 B**（改 plugin）：

```sql
-- 服务器上
sudo mysql -e "ALTER USER 'fitforge'@'localhost' \
    IDENTIFIED WITH mysql_native_password BY 'lhr076200'; \
    FLUSH PRIVILEGES;"
```

**为什么选 B 不选 A**：

- 服务器已经装好 fitforge 库（之前 D26 决策）
- 改 plugin 1 行 SQL 解决
- 不需要装额外包

**但本地 Docker MySQL**用了**方案 C**（启动参数）：

```bash
docker run -d --name fitforge-mysql -p 3307:3306 \
  -v mysql_data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD=root_dev_password_2026 \
  -e MYSQL_DATABASE=fitforge \
  mysql:8.0 \
  --default-authentication-plugin=mysql_native_password
```

## 5. 经验教训


| 教训                                            | 适用场景         |
| --------------------------------------------- | ------------ |
| MySQL 8 部署时**强制考虑认证方式**                       | 任何新部署        |
| pymysql + MySQL 8 = 必须装 cryptography          | 用 pymysql 必踩 |
| asyncmy + caching_sha2 = **也是** 报错            | async 驱动同样问题 |
| `--default-authentication-plugin` 只对**新用户**生效 | 容器化部署        |


## 6. 面试话术

### Q1：MySQL 8 怎么连不上？报 cryptography 错误？

> "MySQL 8 默认 caching_sha2_password 认证——新协议用 RSA 加密握手，pymysql 不内置。**两种解法**：① 装 `cryptography` 包（推荐，不动 MySQL）；② 改 user plugin 为 `mysql_native_password`（老协议，pymysql 直接支持）。我选的是改 plugin——服务器 fitforge 用户已经建好，一条 SQL 解决。"

### Q2：为什么 MySQL 8 改用 caching_sha2_password？

> "MySQL 5.7 之前用 mysql_native_password（SHA1 哈希），8.0 改 caching_sha2_password（缓存 RSA 加密）。**安全更强**（每次连接用不同公钥、防重放），但**兼容性差**（老客户端不支持）。生产环境如果客户端全是新代码就保留，新老混用就改回老协议。"

### Q3：--default-authentication-plugin 跟 ALTER USER 区别？

> "`--default-authentication-plugin` 是 MySQL 启动参数，**只影响新创建的用户**（CREATE USER 时的默认 plugin）。已存在的用户**不会变**。要改老用户必须 `ALTER USER ... IDENTIFIED WITH`。两个是不同时间维度的：启动时定 default，运行时改 specific。"

## 7. 复现 + 验证步骤

```bash
# 复现：让 fitforge 用户用 caching_sha2
sudo mysql -e "ALTER USER 'fitforge'@'localhost' \
    IDENTIFIED WITH caching_sha2_password BY 'lhr076200'; \
    FLUSH PRIVILEGES;"

# 验证报错
python -c "
import pymysql
try:
    pymysql.connect(host='localhost', port=3306, user='fitforge',
        password='lhr076200', database='fitforge')
except RuntimeError as e:
    print(f'报错：{e}')
# 预期：'cryptography' package is required for sha256_password
#        or caching_sha2_password auth methods

# 修复：装 cryptography
pip install cryptography

# 验证成功
python -c "
import pymysql
conn = pymysql.connect(host='localhost', port=3306, user='fitforge',
    password='lhr076200', database='fitforge')
print('connected OK')
"
```

## 8. 相关文档

- `tech_notes/2026-07-06-docker-mysql-volume.md`（本地 Docker 部署）
- `tech_notes/2026-08-13-server-deploy-record.md`（服务器端到端）
- `docs/deploy-to-server.md`（部署清单）

---

**沉淀状态**：✅ 用户于 2026-08-13 批准落盘