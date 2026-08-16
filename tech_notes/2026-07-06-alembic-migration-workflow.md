# Alembic Migration Workflow 沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D9（Alembic schema 版本管理）、D17（3 张表 schema）、D26（容器化 + Volume）
> **关联 commit**：`2deddcb`（Task 10 alembic init）、`fff8b3d`（Task 11-13 autogenerate + upgrade）
> **目的**：面试前复习 + Alembic 工程实践

---

## 1. 为什么需要 Alembic（数据库的后悔药和历史书）


| 不需要 Alembic                                                                    | 需要 Alembic                                                     |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| 单人 demo、本地玩玩                                                                   | 团队多人协作                                                         |
| DB schema 不变                                                                   | schema 频繁迭代                                                    |
| 部署环境单一                                                                         | 多个环境（dev/staging/prod）                                         |
| 问题你在本地数据库建了张表，第二天换个电脑，或者同事拉了你的代码，他那里没有这张表，程序就崩了。 或者，你给表加了个字段，上线时忘了加，网站直接 404。 | 你加个字段，它生成一个文件。同事拿到文件，运行命令，他的数据库也加了这个字段。上线时，自动运行命令，线上数据库也同步了。 |


**核心价值**：把 DB schema（数据库表） 当代码一样版本管理——`schema 变更 = migration 文件`，每个文件有 `upgrade()` 和 `downgrade()`。你运行命令，Alembic 生成了一个文件：`123_add_phone_column.py`。

文件内容大概意思是：“把这个文件给别人跑一下，就能加上 `phone` 字段”。

1. 你把这个 `.py` 文件提交到 Git。
2. **同事**拉取代码，不仅拉到了业务代码，还拉到了这个 `123_add_phone_column.py`。
3. 同事运行命令：`alembic upgrade head`。
4. 这个命令会自动执行那个 `.py` 文件。
5. 同事的数据库就自动加上了 `phone` 字段。
6. 同事再运行代码，**完美运行！**

而这个文件是一直躺在代码库里面的，方便新人同事拉取数据库的时候能拉取到相应的字段，也是项目的成长日记，同时这个文件数据库读取一次之后就不会重复读取，会标记为已读，从而防止重复建表。

> **面试话术**：「数据库 schema 也要版本管理——这是我从 Git 推出来的类比。Alembic 让 schema 变更可追溯、生产部署可控、周五加表不会变成'我忘了在本地加那个字段'的事故。这是数据库领域 DevOps 化的标志。」

---

## 2. alembic env.py 3 个关键设置（alembic的控制中心）

```python
# alembic/env.py（手工编辑，alembic upgrade 不覆盖）

# 1. 注入 SQLAlchemy URL（绕开 alembic.ini 含明文密码）
#告诉 Alembic：“去哪里连数据库”。
from core.config import settings
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)

# 2. 设置 target_metadata（让 autogenerate 能对比 ORM 和 DB）
#告诉 Alembic：“现在的表应该长什么样，全在这个 Base.metadata 里”。
from models import Base  # noqa: F401
target_metadata = Base.metadata

# 3. 触发 model 注册（如果没 import，Base.metadata 是空 MetaData
#你得先引入 User、UserGoal 这些模型，上面的 Base.metadata 里才有东西。
```

**为什么 3 个都关键**：


| 缺失    | 后果                                       |
| ----- | ---------------------------------------- |
| 没有 #1 | alembic.ini 含明文密码（安全风险）                  |
| 没有 #2 | autogenerate 不工作（不知道 ORM 模型有哪些表）         |
| 没有 #3 | Base.metadata 是空 MetaData（3 个 model 没注册） |


> **面试话术**：「alembic env.py 我做 3 个改动：① 注入 URL 到 config（避免明文密码）；② 设 target_metadata（让 autogenerate 能 diff）；③ import models 触发注册。这是 alembic 标准模板的 3 个关键 hook，缺一不可。」

---

## 3. autogenerate 的工作机制（自动比对，生成“装修单”）

```
alembic revision --autogenerate -m "create users"
   ↓
对比：
   Base.metadata（ORM 端的 schema，3 个 model）
   vs
   DB schema（SHOW CREATE TABLE / information_schema.COLUMNS）
   ↓
生成 diff：
   Detected added table 'users'
   Detected added index 'ix_users_email' on 'email'
   ↓
生成 op.create_table / op.create_index 代码
   ↓
写入 alembic/versions/<hash>_create_users.py（也就是存到alembic里面作为数据库的更改文件）
```

### 3.1 autogenerate 能识别的变更


| 变更            | alembic autogenerate 是否识别 |
| ------------- | ------------------------- |
| 加表            | ✅ 识别                      |
| 加列            | ✅ 识别                      |
| 改列类型          | ✅ 识别                      |
| 加索引           | ✅ 识别                      |
| 删表 / 删列 / 删索引 | ✅ 识别（生产慎用）                |
| FK + CASCADE  | ✅ 识别                      |


### 3.2 autogenerate **不能识别**的变更（手工补充）


| 变更                                              | 原因                                                                                                                                                                                                                                                                                        | 解法                                                                                 |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **ENUM 加值**                                     | MySQL ENUM 是字符串，autogenerate 比对字符串内容失败                                                                                                                                                                                                                                                    | 手写这行 SQLop.execute("ALTER TABLE users MODIFY COLUMN gender ENUM('男', '女', '保密')") |
| **CHECK 约束****场景**： 你想规定“年龄”字段，必须大于 0 岁。不能存负数。 | 部分识别但可能漏                                                                                                                                                                                                                                                                                  | # 手写代码加约束op.create_check_constraint("check_age_positive", "users", "age > 0")    |
| **视图 / 触发器 / 存储过程**                             | autogenerate 只看表结构                                                                                                                                                                                                                                                                        | 手写 `op.execute(...)`                                                               |
| **重命名（保留数据）**                                   | **场景**： `username` 想改名叫 `login_name`。**Alembic** 它看代码：有 `login_name`，它看数据库：有 `username`。它想：“代码里没 `username`，数据库里有——那就是**删了**！代码里有 `login_name`，数据库里没——那就是**新建**！”**它会生成什么？**- 删掉 `username` 列。- 新建 `login_name` 列。- 你原本 `username` 里存着“张三、李四”几万条数据。 Alembic 一执行：“好，删掉旧列（数据全扔了），新建个空列。” | 手写 `op.alter_column(...)` + 数据迁移 SQL                                               |
| **RENAME TABLE（表改名）**                           | 识别成 drop + create                                                                                                                                                                                                                                                                         | 手写 `op.rename_table(...)`                                                          |


> **面试话术**：「Alembic autogenerate 不是万能——它识别不了 ENUM 加值、视图、触发器、复杂重命名。每次 autogenerate 后都要人工 review，必要时手写 SQL。我项目里每次 autogenerate 后 review 生成的 migration 文件，确认 UNIQUE 约束、CASCADE、ENUM 都正确。」

---

## 4. 3 套概念区分


| 概念                       | 作用                                                          |
| ------------------------ | ----------------------------------------------------------- |
| **model（设计图纸）**          | Python 代码，定义 ORM 类（下次 schema 变更要改的地方）                       |
| **migration（施工记录单）**     | Alembic 文件夹，Python 文件，记录 schema 变更历史（含 upgrade + downgrade） |
| **alembic_version（进度条）** | DB 里的 1 行表，记录当前应用的 revision ID，记录当前装修进行到第几步了                |


```
model (Python)
   ↓ autogenerate
migration (Python)
   ↓ upgrade head（按单施工）
DB schema + alembic_version (SQL)
```

**alembic_version 表示什么**：

```sql
mysql> SELECT * FROM alembic_version;
+-------------+
| version_num |
+-------------+
| ec5983897455 |
+-------------+
```

alembic工作过程：

- **阶段一：初始化**
  - 你写好 Model。
  - 运行 Alembic -> **数据库里诞生了第一张表。**
- **阶段二：开发中**
  - 你想给 User 加个 `phone` 字段。
  - 修改 Model。
  - 运行 Alembic -> **数据库里的表多了一个字段。**

从头到尾，只要涉及数据库结构的变化，不管是“从无到有”，还是“从有到变”，**都得听 Alembic 的指挥**。这样你的代码和数据库才能永远保持同步。

这就是当前 DB 应用的 migration ID。`alembic upgrade head` 会找到所有未应用的 migration（`version_num` 之后的），依次执行。

---

## 5. 我们项目的 4 个工程决策

### 5.1 一次 autogenerate 生成 3 张表

**plan 原写**是 3 次分开 autogenerate（每次一张表），**实际执行**是 1 次 autogenerate 生成所有 3 张表。

**理由**：

- 这三张表是缺一不可的相互有联系，如果遗漏·了 ****`user_goals`：你的代码里写了“用户可以选择目标”的逻辑，代码会去查 `user_goals` 表。如果这张表不存在，程序一启动就崩了，或者一点击就报错。
- 业内标准：一次 autogenerate 一个 revision 的所有表
- 省人工 review 成本：1 次 review vs 3 次 review
- 生产部署更简洁：1 个 migration revision vs 3 个
- 所以，把它们放在同一个迁移文件里，要么一起建，要么一起不建，**能保证你的系统每时每刻都是完整的、能跑起来的。**

### 5.2 `SYNC_DATABASE_URL`（pymysql同步）而非 `DATABASE_URL`（asyncmy异步）

```python
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)
```

**为什么 alembic 用同步 URL**：

- alembic autogenerate 是同步流程——它执行 `SHOW CREATE TABLE`、`SELECT FROM information_schema` 等元数据查询
- 用 asyncmy 配置复杂（需要 event loop、async session），易踩坑
- alembic 一生只跑几次（部署时），性能不是瓶颈，因为大多数时候都是在本地调试表，用的是本地的数据库，合适的才部署到线上，因此线上调试的次数不多用同步

**这里vs fastAPI：**

- **动作**：FastAPI 响应用户请求，比如“注册一个用户”。
- **方法**：因为要追求高并发、快速度，它用的是**异步**机制（`async/await`）。
- **表现**：代码里写着 `session.add(user)`，底层用的是 `aiomysql` 驱动。

也就是fast API和alembic都是需要对数据库进行操作的，但前者是对数据库的增删改查操作，也就是负责操作数据内容，因此要用到异步对数据库进行访问；而后者是对数据库表的结构，建表进行操作，这个频率比较小所以用同步来完成

### 5.3 alembic.ini 不含明文密码

```ini
# alembic.ini
# sqlalchemy.url is injected by alembic/env.py from core.config.settings.SYNC_DATABASE_URL
# (avoid plaintext password in alembic.ini)
# sqlalchemy.url = driver://user:pass@localhost/dbname
```

URL 由 env.py 注入到 config，alembic.ini 里只留注释。

### 5.4 alembic.ini 不能含中文（Windows GBK 编码坑）

configparser 默认按 GBK 读 .ini 文件——中文注释会导致：

```
UnicodeDecodeError: 'gbk' codec can't decode byte 0xb1 in position 2566
```

**解法**：alembic.ini 用英文注释（Python 文件用 UTF-8 没问题，ini 文件用 GBK 是 Python 老问题）。

---

## 6. Alembic 实战命令清单

```bash
# 初始化（一次性）
alembic init alembic                       # 创建 alembic/ 目录 + alembic.ini

# 配置 env.py（手工改）

# 日常 workflow
alembic revision --autogenerate -m "msg"   # 生成 migration（diff ORM vs DB）
alembic revision -m "msg"                  # 手写空 migration（无 autogenerate）
alembic upgrade head                       # 应用所有未执行的 migration
alembic upgrade +1                         # 应用下一个 revision
alembic downgrade -1                       # 回滚上一个 revision
alembic current                            # 看当前应用的 revision
alembic history                            # 看所有 revision 历史
alembic history --verbose                  # 看每个 revision 的详细信息
alembic stamp head                         # 把 alembic_version 标记为最新（不跑 SQL）

# 调试
alembic upgrade head --sql                 # 只打印 SQL 不执行（先看再跑）
alembic upgrade head --dry-run             # 试运行（生成但不写文件）
```

> **面试话术**：「Alembic 实战命令就 3 类：① `revision --autogenerate` 生成；② `upgrade head` 应用；③ `current/history` 看状态。`--sql` 和 `--dry-run` 是调试神器——生成 migration 后先看 SQL 再跑，避免线上事故。」

---

## 7. 完整 alembic workflow（fitforge 实例）

```bash
# 1. 修改 model
edit models/user.py  # 加新字段

# 2. autogenerate 生成 migration
#Alembic 只是看了看你的代码，把要改的东西写进了那个 .py 文件 里。
alembic revision --autogenerate -m "add phone column to users"

# 3. 检查生成的 migration（人工 review）
cat alembic/versions/<hash>_add_phone_column_to_users.py

# 4. 测试环境先跑（因为alembic.ini 这个配置文件里的sql的url地址是本地的所以这里操控的是本地的）
alembic upgrade head

# 5. 本地验证：表结构对吗？数据还在吗？
python -c "from sqlalchemy import create_engine; e = create_engine('...'); print(e.dialect.reflect(...))"

# 6. commit + 部署
git add alembic/versions/ && git commit -m "feat(db): add phone column"
git push  # 部署时自动跑 alembic upgrade head
```

> **面试话术**：「Alembic 工作流：① 改 model；② autogenerate 生成 migration；③ 人工 review 生成的 SQL；④ 本地 upgrade 测试；⑤ 确认无误后 commit + push。这是 schema 变更的标准流程，每个步骤都不能跳——尤其是 review，autogenerate 漏改 ENUM 是常见坑。」

---

## 8. 面试 Q&A（5 题预演）

### Q1：为什么要 Alembic？

> "数据库 schema 也要版本管理——把 schema 当代码一样管。Alembic 让 schema 变更可追溯、生产部署可控、团队协作不冲突（不会'我忘了在本地加那个字段'）。这是数据库领域 DevOps 化的标志，跟 Git 管理代码一个逻辑。"

### Q2：alembic autogenerate 能识别所有变更吗？

> "不能。它识别不了 ENUM 加值、视图、触发器、复杂重命名（RENAME 会识别成 DROP + CREATE 丢数据）。autogenerate 完必须人工 review，必要时手写 SQL——alembic 提供 op.execute() 跑原始 SQL 补齐。"

### Q3：为什么 alembic 用 pymysql（同步）不用 asyncmy（异步）？

> "alembic autogenerate 是同步流程——跑 SHOW CREATE TABLE、information_schema 查询，对比 ORM metadata。配置 asyncmy 需要 event loop、async session，复杂度高、易踩坑。alembic 一生只跑几次（部署时），性能不是瓶颈。'工具与运行时分离'——FastAPI 用 asyncmy 跑业务，alembic 用 pymysql 跑迁移。」

### Q4：alembic_version 表是怎么用的？

> "它是 1 行 1 列的表，存当前应用的 revision ID（如 `ec5983897455`）。`alembic upgrade head` 会查 alembic_version 找当前 revision，然后跑所有未应用的 migration。`alembic current` 看当前 revision、`alembic history` 看所有历史 revision。这个机制让 rollback 也安全——`alembic downgrade -1` 回滚上一个，alembic_version 自动更新。」

### Q5：alembic.ini 能含数据库密码吗？

> "不能——alembic.ini 应该提交到 Git。我把 URL 注释掉，由 env.py 从 pydantic-settings 读 SYNC_DATABASE_URL。这样密码只在 .env 里（不入 Git）。生产部署时 .env 由密钥管理系统注入，不进任何配置文件。」

---

## 9. 踩坑清单


| 坑                         | 现象                         | 解法                                  |
| ------------------------- | -------------------------- | ----------------------------------- |
| 1.4 旧版 alembic API        | `op.create_table` 缺参数      | 升级到 alembic 1.14+，用新 API            |
| autogenerate 后忘了 review   | ENUM 加值失败 / 索引漏建           | 每次 autogenerate 后 review            |
| revision 文件命名不规范          | `xxxx_create_users.py` 难识别 | 用 `-m "create users table"` 命名      |
| 不写 downgrade              | 回滚失败                       | migration 必须含 downgrade()           |
| alembic.ini 含中文           | UnicodeDecodeError GBK     | 用英文注释                               |
| env.py 没设 target_metadata | autogenerate 不工作           | 设 `target_metadata = Base.metadata` |
| alembic.ini 含明文密码         | 密码入 Git 仓库                 | 注释掉，由 env.py 注入                     |
| 生产部署忘记跑 alembic upgrade   | schema 不一致                 | 加到 CI/CD 流水线自动跑                     |


---

## 10. 参考资源

- [Alembic 官方文档](https://alembic.sqlalchemy.org/en/latest/)
- [Alembic autogenerate 详解](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [SQLAlchemy 2.0 Alembic 集成](https://docs.sqlalchemy.org/en/20/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)
- [生产部署 Alembic 实践](https://github.com/zalando-incubator/cookiecutter-flask/blob/master/%7B%7Bcookiecutter.repo_name%7D%7D/docs/_build/html/deploying.html)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘