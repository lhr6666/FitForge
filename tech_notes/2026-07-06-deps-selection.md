# FitForge 13 个核心依赖选型沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D4（SQLAlchemy 异步）、D6（Argon2id）、D9（Alembic）、D11（pydantic-settings）、D19（6 决策）
> **关联 commit**：`f658413`（plan Task 1）
> **目的**：面试前复习 + 团队 wiki 参考

---

## 1. 13 个核心依赖全景（按职责 5 类）


| 类别           | 包                   | 版本      | 作用                                    |
| ------------ | ------------------- | ------- | ------------------------------------- |
| **Web 框架**   | fastapi             | 0.115.6 | Web 框架（路由 + Depends + OpenAPI）        |
|              | uvicorn[standard]   | 0.32.1  | ASGI 服务器（含 httptools/uvloop/watchgod） |
| **ORM + DB** | sqlalchemy[asyncio] | 2.0.36  | 异步 ORM（D4 决策）                         |
|              | asyncmy             | 0.2.10  | MySQL 异步 DBAPI 驱动                     |
|              | pymysql             | 1.1.1   | MySQL 同步 DBAPI（Alembic 用）             |
|              | alembic             | 1.14.0  | schema 版本管理（D9 决策）                    |
| **数据校验**     | pydantic[email]     | 2.10.4  | 数据校验 v2（性能 5-50x）                     |
|              | pydantic-settings   | 2.7.0   | 从 .env 读配置（D11 决策）                    |
|              | email-validator     | 2.*     | EmailStr 依赖                           |
|              | python-multipart    | 0.0.20  | 表单/OAuth2 依赖                          |
| **安全**       | passlib[argon2]     | 1.7.4   | 密码哈希统一接口（D6 决策）                       |
|              | argon2-cffi         | 23.1.0  | Argon2 C 实现（passlib backend）          |
| **测试**       | pytest              | 9.1.1   | 测试框架                                  |
|              | pytest-asyncio      | 1.4.0   | 异步测试支持                                |
|              | httpx               | 0.28.1  | 异步 HTTP 客户端（端到端）                      |


---

## 2. 4 个核心原理 + 面试话术

### 2.1 SQLAlchemy[asyncio] + asyncmy 双层架构

**原理**：SQLAlchemy 自己**不直接发 SQL**——它通过 DBAPI 驱动跟 MySQL 通信。

```
应用代码
   ↓ await
SQLAlchemy Core/ORM（高层抽象）
   ↓ 翻译成 SQL
DBAPI 驱动（asyncmy，底层 TCP 协议）
   ↓
MySQL Server（3306 端口）
```

**面试话术**：

> "SQLAlchemy 自己不发 SQL——它通过 DBAPI 驱动跟 MySQL 通信。`[asyncio]` extras 启用异步扩展，asyncmy 是异步 DBAPI 驱动，所以整条链路都是非阻塞。这是 SQLAlchemy 2.0 的设计：把'ORM 抽象'和'驱动'两层完全解耦，未来换 PostgreSQL 只换 asyncpg 即可，ORM 代码不动。"

---

### 2.2 Alembic 用 pymysql（同步）而非 asyncmy

**原理**：Alembic **autogenerate 是同步流程**——它执行 `SHOW CREATE TABLE`、`SELECT FROM information_schema` 等元数据查询，对比 ORM metadata 和 DB schema 生成 diff。Alembic 是 Python 的“数据库版本控制工具”，类似 Git 管理代码，管理数据库表结构的变化

**为什么用同步驱动**：

1. alembic 命令是 CLI 工具，运行时是**进程级同步**——不必异步
2. 用 asyncmy 配置更复杂（需要 event loop、async session），易踩坑
3. alembic 一生只跑几次（部署时），性能不是瓶颈
4. **运行时（FastAPI）用 asyncmy**，**离线工具（alembic）用 pymysql**——关注点分离

**面试话术**：

> "Alembic migration 是离线工具，跟运行时解耦——用同步驱动更简单可靠，避免双重异步配置踩坑。这是工程上的'工具与运行时分离'原则：alembic 一生跑几次，FastAPI 每秒跑几千次，两者用不同驱动完全合理。"

---

### 2.3 passlib[argon2] + argon2-cffi 分层设计

**原理**：

- **passlib**：上层密码哈希库，统一 API（`hash()`、`verify()`），支持 bcrypt/scrypt/argon2/pbkdf2 等多种算法
- **argon2-cffi**：Argon2 算法的 **C 实现**（passlib 的 backend）

**为什么两个都要装**：

- 不装 argon2-cffi → passlib 回退到**纯 Python 实现**，慢 100 倍且不安全
- `passlib[argon2]` extras 触发 pip 自动装 argon2-cffi（声明依赖）

**面试话术**：

> "passlib 是接口、argon2-cffi 是实现——分层设计让 passlib 可换 bcrypt/scrypt/argon2 不同 backend。部署时一定两个都装，且用 `[argon2]` extras 而不是单独装 passlib，避免漏装 C 实现。Argon2id 是 OWASP 2023+ 推荐的 PHC 算法，比 bcrypt 抗 GPU/ASIC 攻击更强——因为它是 memory-hard（内存硬性）的，硬件加速成本高。"

---

### 2.4 版本锁定策略（==）vs 范围（*）混用

**原则**：**按风险分级**。


| 风险等级        | 用法            | 示例                                                       |
| ----------- | ------------- | -------------------------------------------------------- |
| **核心安全/架构** | `==X.Y.Z` 锁版本 | fastapi, sqlalchemy, alembic, passlib, pydantic-settings |
| **次要工具/库**  | `X.`* 范围版本    | email-validator, python-multipart                        |


**理由**：

- 锁版本 = **可重现部署**（生产必须——一次打包出包，下次部署一模一样）
- 范围版本 = **自动吃补丁**（次要包省心——bugfix 自动更新，无需 PR）

**面试话术**：

> "核心安全/架构相关锁版本，次要工具用范围——按风险分级。requirements.txt 不是 lock file（不像 poetry.lock 或 uv.lock），是'依赖清单'：声明依赖但允许灵活版本。要真锁全版本得用 `pip freeze > requirements-lock.txt`，部署时用 lock 文件。但 MVP 阶段 `==` 已经够稳。"

---

## 3. 面试 Q&A（4 题预演）

### Q1：为什么要异步 ORM？同步 ORM 不也能用吗？

> "能用，但 FastAPI 是 async 框架——同步 ORM 会**阻塞事件循环**。高并发下，一个 100ms 的慢查询会卡住整个服务器所有请求。异步 ORM 让出控制权，期间服务器能处理其他请求。这是 FastAPI 选异步生态的核心理由——不是炫技，是**架构一致性**。"

### Q2：passlib 为什么还要装 argon2-cffi？装 passlib 不够吗？

> "不够。passlib 是接口层（`CryptContext`），argon2-cffi 是实现层（Argon2 的 C 绑定）。不装 argon2-cffi，passlib 会回退到**纯 Python 实现**——慢 100 倍且不安全（容易受 timing attack）。两者是 **interface-impl 分层**，类似 SQLAlchemy/asyncmy 的关系。"

### Q3：requirements.txt 是 lock file 吗？

> "不是。requirements.txt 是'依赖清单'，声明依赖但允许灵活版本（`X.`* 或 `>=X.Y`）。lock file 是 poetry.lock / uv.lock / pip-tools 生成的——锁**完整依赖树**（含传递依赖），保证 A 机器和 B 机器装出来的环境字节级一致。MVP 阶段用 `==` 已经够稳；要做生产部署，建议加 `pip freeze > requirements-lock.txt`。"

### Q4：怎么升级依赖？

> "三步走：① 看 changelog 评估风险；② 改 requirements.txt 版本号；③ 跑测试套件验证。核心包升级要走单独 PR——不能跟业务代码混在一起 commit，方便回滚。生产环境升级前要在 staging 跑 24 小时 soak test。"

---

## 4. 踩坑清单（提前预警）


| 坑                     | 现象                                                      | 解法                                               |
| --------------------- | ------------------------------------------------------- | ------------------------------------------------ |
| 漏装 `[asyncio]` extras | `ImportError: No module named 'sqlalchemy.ext.asyncio'` | 装 `sqlalchemy[asyncio]` 不是 `sqlalchemy`          |
| 漏装 `[argon2]` extras  | `passlib.hash.argon2` 报 backend 错误                      | 装 `passlib[argon2]` 不是 `passlib`                 |
| pydantic v1/v2 混用     | 老代码报 `validator` 不存在                                    | v2 用 `field_validator`，v1 用 `validator`——v2 重命名了 |
| email-validator 漏装    | `EmailStr` 报 `email-validator` not installed            | 装 `pydantic[email]` 不是 `pydantic`                |


---

## 5. 参考资源

- [SQLAlchemy 2.0 异步文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic 教程](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Pydantic v2 迁移指南](https://docs.pydantic.dev/latest/migration/)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘