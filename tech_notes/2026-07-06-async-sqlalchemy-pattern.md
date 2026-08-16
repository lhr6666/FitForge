# async SQLAlchemy 模式沉淀

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D4（SQLAlchemy 2.0 异步 + asyncmy）、Q3（async generator + Depends）
> **关联 commit**：`c7dfaa0`（plan Task 3）
> **目的**：面试前复习 + async ORM 工程原则

---

## 1. async_sessionmaker 的"工厂的工厂"模式

```python
# 第一步：创建工厂（模块加载时执行一次）
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# 第二步：调用工厂拿 session（每个请求一次）
async with AsyncSessionLocal() as session:
    ...
```

**"工厂的工厂"本质**：async_sessionmaker 本身不是 session，是一个**生产 session 的工厂**。调用 `AsyncSessionLocal()` 才是真正创建 session 实例。

**为什么这种设计？**


| 设计选择     | 优点                                                         |
| -------- | ---------------------------------------------------------- |
| **配置集中** | session 的 `expire_on_commit`、`autoflush`、`class`_ 在工厂创建时定好 |
| **调用简洁** | `AsyncSessionLocal()` 一行拿 session，不用每次传 engine 和参数         |
| **解耦**   | 换 engine 不影响调用处代码                                          |


> **面试话术**：「SQLAlchemy 的 sessionmaker 是'工厂的工厂'——这是设计模式里的'抽象工厂'。配置一次、调用多次，避免重复参数。session = async_sessionmaker(...)() 这种写法面试会被追问，可以反过来说'我更喜欢分两步写，可读性更高'。这是 SQLAlchemy 区别于手写 DBUtils 的优雅之处。」

---

## 2. expire_on_commit=False：异步 ORM 的**强制设置**


| expire_on_commit | 同步 session               | 异步 session                                                     |
| ---------------- | ------------------------ | -------------------------------------------------------------- |
| **True（默认）**     | ✅ OK（lazy load 触发隐式 SQL） | ❌ **报错**：`MissingGreenlet: greenlet_spawn has not been called` |
| **False**        | ✅ OK（commit 后属性保留快照）     | ✅ **OK**                                                       |


**为什么异步不能 lazy load**：

```python
# 同步代码：程序停在这里等
user = db.query(User).first()  # 程序卡在这里，等数据库返回
print(user.name)               # 数据返回后才执行这行

# 异步代码
user = await db.get(User, 1)  # ✅ 查数据库，用 await 等待
await db.commit()             # ✅ 提交，用 await 等待

print(user.name)  # ❌ 报错！MissingGreenlet

```

user.name这种属于属性访问，user.get_name()带括号的就是函数调用，**属性访问**：就像"看一眼"，直接拿数据，没有括号 `()`**函数调用**：就像"下命令"，执行一段代码，有括号 `()。`

`await` 的意思是：“暂停当前函数，等这个异步操作完成”。但 `user.name` 根本不是一个异步操作，它只是"看一眼"

你不能说"暂停当前函数，等我看一眼完成"——看一眼是一瞬间的事。

所以只有设false，*commit 不会清空 user 对象的数据，而是保留快照下次查询直接返回快照*

**设 False 的代价**：

- commit 后如果改了 DB 数据，ORM 对象**不感知**（返回 commit 时的快照），也就是返回改动之前的旧数据
- 但在**事务内**不会发生（同一 session 一直生效）
- 跨 session 操作需要 `db.refresh(obj)`

> **面试话术**：「expire_on_commit=False 是**异步 ORM 的强制设置**——因为 Python 属性访问 `user.orders` 不能 `await`，而 lazy load 本质是隐式 await。设 False 后，commit 时把数据快照住，访问属性直接返回快照不再查 DB。代价是：commit 后改 DB 数据，ORM 对象不感知——但这在事务里不发生（事务内同一 session 一直生效）。面试追问'为什么不 eager load 解决'——答：eager load 会一次性 JOIN 所有 relationship，N+1 问题更严重；False 是 lazy load 与 eager load 的折中。」

---

## 3. pool_pre_ping=True：生产环境的"连接体检"

**核心概念**：防止拿到一个“断开”的连接。

**问题根源**：MySQL 默认 `wait_timeout = 28800 秒（8 小时）`——空闲连接会被服务端关闭。中间件/防火墙也可能断开空闲连接。

**典型错误**：

```python
# 早上 9 点：服务启动，连了 10 个连接进连接池
# 中午 12 点：3 小时空闲，MySQL 服务端悄悄关掉了这 10 个连接
# 下午 1 点：第一个请求拿连接 → 报错
sqlalchemy.exc.OperationalError: (MySQLdb.OperationalError) (2006, "MySQL server has gone away")
```

**pool_pre_ping=True 解法**：

```
请求进入
   ↓
从连接池拿连接
   ↓
发一个SELECT 1（pre_ping 检查）  ← 这里花 ~1ms
   ├ 有反应：连接有效 → 用连接
   └ 没反应：连接断开 → 丢弃，重连
   ↓
执行业务 SQL
```

**代价与收益**：


| 维度     | 数值                 |
| ------ | ------------------ |
| **代价** | 每次拿连接多 ~1ms（毫秒级开销） |
| **收益** | 零"连接已断开"错误         |
| **适用** | 生产必开，开发可关          |


> **面试话术**：「pool_pre_ping 是生产必开——MySQL 8 小时断开空闲连接、中间件/防火墙也经常断开。1ms 的 ping 成本换来零'MySQL server has gone away'错误，是典型的'小成本换大可靠性'工程实践。开发环境可以关掉省 1ms，生产环境必开——这是 SQLAlchemy 文档明确推荐的。」

---

## 4. get_db：async generator + HTTP 请求绑定

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:  # 1. 拿一个盘子
          try:
              yield session  # 2. 把盘子递给做奶茶的人（路由函数）
          except:
              await session.rollback() # 3. 出错了？把盘子里的东西倒掉（回滚）
              raise
          finally:
              pass  # 4. 无论成功失败，finally 都会执行，async with 会自动把盘子收走
```

**关键点：yield 是什么？**

- `yield` 就像**传菜员把盘子递给厨师**。
- 传菜员停在原地不动，等厨师把菜做好了，盘子回到传菜员手里。

**完整生命周期**：

```
HTTP 请求进入
   ↓
FastAPI 解析 Depends(get_db)
   ↓
get_db() 执行到 yield session
   ↓
路由函数 await auth_service.register(db, user_create)
   ↓
HTTP 请求结束
   ├ 成功 → yield 正常返回 → finally → async with close
   └ 失败 → except rollback → finally → async with close
       → raise → FastAPI exception_handler → 409/500 响应
```

**4 个设计要点**：


| 要点                      | 作用                                     |
| ----------------------- | -------------------------------------- |
| **async with**          | 自动 close session，避免泄漏                  |
| **try/except/rollback** | 事务原子性——部分写入撤销                          |
| **raise**               | 把异常重新抛出，让 FastAPI exception_handler 处理 |
| **finally**             | 即使异常也走 close（即使 raise 也会触发）            |


**为什么用 async generator 不用普通函数？**

```python
# ❌ 普通函数：无法在 finally 里 close
async def get_db() -> AsyncSession:
    session = AsyncSessionLocal()
    return session  # 没有 finally 关闭！连接泄漏！

# ✅ async generator：yield 暂停后能执行 finally
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # 路由函数结束后才执行这里
            ...
```

> **面试话术**：「session 生命周期与 HTTP 请求绑定——每个请求独立 session，天然隔离并发。async generator 是 FastAPI 推荐的依赖注入模式，比'中间件 + request.state.db'显式 10 倍，比'全局单例 session'安全 100 倍。核心是 generator 的 yield/finally 协议——yield 把控制权交给路由函数，路由函数结束后 finally 清理资源。这是 Python 协程+依赖注入的最佳实践。」

---

## 5. 面试 Q&A（4 题预演）

### Q1：**为什么不用指定连接池类型？**

A: SQLAlchemy 会自动选最适合异步的连接池，不用你操心。

### Q2：expire_on_commit=False 是什么意思？为什么异步必须设？

> "expire_on_commit=False 是 Pydantic/SQLAlchemy 的一个设置——commit 后不让 ORM 对象属性 expire（重新查询 DB）。同步 session 设 True 也行（lazy load 兼容），但异步 session 设 True 会报 `MissingGreenlet`——因为 Python 属性访问不能 await，而 lazy load 本质是隐式 await。设 False 后，commit 时把数据快照住，访问属性直接返回快照不再查 DB。"

### Q3：pool_pre_ping=True 的代价？

> "每次从连接池拿连接前发 SELECT 1，~1ms 开销。换来零'MySQL server has gone away'错误。生产环境必开，开发环境可关省 1ms。这是'1ms 换可靠性'的典型工程权衡。"

### Q4：get_db 为什么用 async generator 而不是普通 async 函数？

> "async generator 的 yield 暂停 + finally 清理协议——路由函数 await session 操作 DB，结束后 yield 抛回 get_db，触发 finally 关闭 session。普通 async 函数没有这个机制——要么忘记关（泄漏），要么要在路由函数里手动 close（破坏抽象）。async generator 是 FastAPI Depends 注入的最佳实践。"

---

## 6. 踩坑清单


| 坑                           | 现象                                      | 解法                                                                   |
| --------------------------- | --------------------------------------- | -------------------------------------------------------------------- |
| 同步 lazy load 失败             | `MissingGreenlet` 报错                    | 异步 ORM 必须 `await db.refresh(obj)` 或用 `selectinload`/`joinedload` 预加载 |
| `expire_on_commit=True`（默认） | commit 后属性访问报错                          | 显式设 `expire_on_commit=False`                                         |
| 不开 `pool_pre_ping`          | "MySQL server has gone away"            | 生产环境加 `pool_pre_ping=True`                                           |
| 连接池耗尽                       | `TimeoutError: QueuePool limit reached` | 调大 `pool_size` + `max_overflow` 或优化慢查询                               |
| 异步 session 用同步 driver       | `MissingGreenlet` + 阻塞                  | 异步 engine 必配 asyncmy/asyncpg                                         |


---

## 7. 参考资源

- [SQLAlchemy 2.0 Async 文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Dependencies 文档](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Python async generator 教程](https://docs.python.org/3/reference/expressions.html#yield-expressions)
- [SQLAlchemy expire_on_commit 设计](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#commit)

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘