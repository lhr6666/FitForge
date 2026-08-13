# /auth/register 完整数据流 + 6 决策回顾

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code 配对沉淀）
> **关联决策**：D19（6 决策）、D26（容器化 + Volume）、D27（密码 lhr076200）
> **关联 commit**：`0cab349`（POST /auth/register 路由）+ 整个 /auth/register 链路
> **目的**：面试前复习 /auth/register 完整链路 + 6 决策回顾

---

## 1. POST /auth/register 完整数据流

```
客户端                  FastAPI                       业务层                       数据库
  │                       │                            │                            │
  ├─ HTTP POST ────────► │                            │                            │
  │  {username,           │                            │                            │
  │   email,              │                            │                            │
  │   password,           │                            │                            │
  │   nickname?}          │                            │                            │
  │                       │                            │                            │
  │                       ├─ Pydantic 校验 ────────────► │                            │
  │                       │  （422 if fail）            │                            │
  │                       │  • username 3-50 字母数字    │                            │
  │                       │  • email EmailStr 必填        │                            │
  │                       │  • password ≥8 + 字母+数字    │                            │
  │                       │                            │                            │
  │                       ├─ Depends(get_db) ──────────► │                            │
  │                       │  注入 AsyncSession            │                            │
  │                       │                            │                            │
  │                       ├─ auth_service.register() ──► │                            │
  │                       │                            ├─ SELECT user WHERE username=?│
  │                       │                            │                            ├─► [DB]
  │                       │                            │   返回：None（不存在）        │
  │                       │                            │                            │
  │                       │                            ├─ SELECT user WHERE email=? │
  │                       │                            │                            ├─► [DB]
  │                       │                            │   返回：None（不存在）        │
  │                       │                            │                            │
  │                       │                            ├─ hash_password(password)   │
  │                       │                            │  Argon2id($argon2id$...)    │
  │                       │                            │                            │
  │                       │                            ├─ User(username=...,       │
  │                       │                            │       password_hash=...,    │
  │                       │                            │       email=...,            │
  │                       │                            │       nickname=...)         │
  │                       │                            │                            │
  │                       │                            ├─ db.add(user)              │
  │                       │                            ├─ await db.flush()           │
  │                       │                            │                            ├─► INSERT INTO users
  │                       │                            │   返回 user.id=1              │
  │                       │                            │                            │
  │                       │                            ├─ await db.commit()          │
  │                       │                            │                            ├─► COMMIT
  │                       │                            │                            │
  │                       │                            └─ return user（ORM 对象）    │
  │                       │                            │                            │
  │                       ├─ UserRead.model_validate(user) ────────────► │
  │                       │  返回 UserRead 实例（id, username, nickname）  │
  │                       │                                            │
  │ ◄── HTTP 201 ────────┤                                            │
  │     {"id":1,          │                                            │
  │      "username":"alice",                                          │
  │      "nickname":null} │                                            │
```

---

## 2. 6 决策回顾（Q1-Q6）

### Q1：重型 service 模式

```python
# ✅ 业务层接 Pydantic schema、返回 ORM、抛业务异常
async def register(db: AsyncSession, user_create: UserCreate) -> User:
    # 业务逻辑（不知道有 HTTP）
    ...
```

**vs 轻型**（业务层接 ORM）：
- ✅ 业务可复用（CLI/脚本/队列都直接调 service.register()）
- ✅ 异常体系清晰（业务异常 vs HTTP 异常解耦）
- ❌ 路由层多做一步 ORM → DTO 转换

### Q2：业务异常体系

```python
# 业务异常继承链
class FitForgeException(Exception): pass
class UsernameExistsError(FitForgeException): pass  # → 路由层 409
class EmailExistsError(FitForgeException): pass     # → 路由层 409

# 路由层 add_exception_handler 自动映射
@app.exception_handler(UsernameExistsError)
async def handler(...): return JSONResponse(409, ...)
```

**关键**：service **不知道 HTTP**！业务层抛业务异常，路由层翻译为 HTTP。

### Q3：async generator + Depends 注入 session

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session       # ← 路由函数开始执行
        except Exception:
            await session.rollback()
            raise
        finally:
            pass  # async with 自动 close
```

**生命周期与 HTTP 请求绑定**——天然隔离并发。

### Q4：2 schema 隔离 password

```python
# UserCreate（请求体）：含 password 明文
class UserCreate(BaseModel):
    password: str = Field(min_length=8)

# UserRead（响应体）：不含 password_hash
class UserRead(BaseModel):
    id: int
    username: str
    nickname: str | None
    # 没有 password_hash → 自动过滤
```

**白名单设计**——比黑名单（手动删字段）安全 10 倍。

### Q5：中等密码强度

```python
@field_validator("password")
@classmethod
def password_must_contain_letter_and_digit(cls, v: str) -> str:
    if not re.search(r"[a-zA-Z]", v):
        raise ValueError("密码必须包含字母")
    if not re.search(r"\d", v):
        raise ValueError("密码必须包含数字")
    return v
```

拦 `12345678`、`abcdefgh` 这类弱密码。

### Q6：强制 email 必填

```python
class UserCreate(BaseModel):
    email: EmailStr  # Q6 强制必填
```

为未来找回密码铺路——MVP 阶段不做，schema 不动。

---

## 3. 关键代码片段（实战参考）

### 3.1 路由层（api/auth.py）

```python
@router.post(
    "/register",
    response_model=UserRead,        # ← Q4: ORM → DTO 自动转
    status_code=status.HTTP_201_CREATED,  # ← RESTful: 创建成功 201
    summary="用户注册",
)
async def register(
    user_create: UserCreate,                       # ← Pydantic 自动校验（422）
    db: AsyncSession = Depends(get_db),            # ← Q3: session 注入
) -> UserRead:
    user = await auth_service.register(db, user_create)  # ← Q1: 重型 service
    return UserRead.model_validate(user)                    # ← Q4: 白名单
```

### 3.2 业务层（services/auth_service.py）

```python
async def register(db: AsyncSession, user_create: UserCreate) -> User:
    # 1. 查重 username → Q2 抛业务异常
    existing = await db.execute(select(User).where(User.username == user_create.username))
    if existing.scalar_one_or_none():
        raise UsernameExistsError(f"用户名 '{user_create.username}' 已被占用")

    # 2. 查重 email
    existing = await db.execute(select(User).where(User.email == user_create.email))
    if existing.scalar_one_or_none():
        raise EmailExistsError(f"邮箱 '{user_create.email}' 已被注册")

    # 3. 哈希密码（Q5: Argon2id 自动加 salt + cost）
    user = User(
        username=user_create.username,
        email=user_create.email,
        password_hash=hash_password(user_create.password),
        nickname=user_create.nickname,
    )

    # 4. 持久化
    db.add(user)
    await db.flush()  # 触发 INSERT，让 DB 填 id / created_at
    await db.commit()
    return user
```

### 3.3 异常映射（api/exception_handlers.py）

```python
@app.exception_handler(UsernameExistsError)
async def username_exists_handler(request: Request, exc: UsernameExistsError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(IntegrityError)  # DB 层兜底（并发场景）
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "数据冲突..."})
```

---

## 4. 5 个核心原理（深度）

### 4.1 数据流 5 层分工

| 层 | 职责 | 不做什么 |
|----|------|---------|
| **客户端** | 发 HTTP 请求 | 不知道 schema |
| **FastAPI 路由层** | HTTP 适配（解析、状态码、ORM → DTO）| 业务逻辑 |
| **Pydantic schema** | 类型校验、自动 422 | DB / 业务 |
| **service 层** | 业务逻辑、抛业务异常 | HTTP 状态码 |
| **ORM 层** | DB 操作 | HTTP / 业务 |

**关键**：每层只关心自己职责，跨层耦合 = 维护灾难。

### 4.2 业务异常自动映射 3 层

```
service 抛 UsernameExistsError
   ↓
路由层 @app.exception_handler(UsernameExistsError)
   ├ 命中 → 409 + 中文 detail
   ↓
未命中？@app.exception_handler(FitForgeException)
   ├ 命中 → 400 + detail
   ↓
未命中？@app.exception_handler(Exception)（FastAPI 默认）
   └ 500
```

**3 层兜底链**——具体异常 → 业务基类 → Exception。

### 4.3 Pydantic 自动 422

```python
@router.post("/register")
async def register(user_create: UserCreate, ...):
    # ↑ FastAPI 解析 body → UserCreate 校验 → 失败自动 422
    # ↑ 业务代码根本不知道校验发生过
```

**链路**：FastAPI 看到类型注解 → 解析 body → Pydantic 校验 → 失败 → 自动 422 + ValidationError 详情 → 业务代码 0 行胶水。

### 4.4 ORM → DTO 白名单设计

```python
# ORM 对象（user 类）: id, username, email, password_hash, nickname, created_at, updated_at
# DTO（UserRead）: id, username, nickname

# 路由层
return UserRead.model_validate(user)  # ORM → DTO，Pydantic 只取 DTO 定义的字段
```

**vs 黑名单**（手动删字段）：
- ❌ `return {k: v for k, v in user.__dict__.items() if k != 'password_hash'}`
- ❌ 容易漏字段、加新敏感字段要改 2 处

**白名单**：UserRead 加字段 = 加要返回的；ORM 加字段 = 自动不返回。

### 4.5 DB 双层兜底

```
应用层（service 查重）→ 99% 拦截 UsernameExistsError
DB 层（UNIQUE 约束）  → 1% 兜底 IntegrityError → 409
```

**为什么需要 DB 层**：并发场景下 2 个请求**同时**通过应用层查重，都不存在，都插入 → DB UNIQUE 约束拒绝其中一个 → 抛 IntegrityError → handler 映射 409。

**纵深防御**：应用层 + DB 层 = 双保险。

---

## 5. 4 状态码含义速查

| 状态码 | 含义 | 触发 |
|--------|------|------|
| **201** | 创建成功 | register 业务成功 |
| **409** | 数据冲突 | username/email 重复（含 DB 兜底）|
| **422** | 请求格式错 | Pydantic 校验失败 |
| **500** | 服务器错 | 未捕获异常 |

---

## 6. 面试 Q&A（5 题预演）

### Q1：/auth/register 完整数据流有几层？

> "5 层分工：客户端 → FastAPI 路由层（HTTP 适配）→ Pydantic schema（自动 422）→ service 层（业务逻辑 + 业务异常）→ ORM 层（DB 操作）。每层只关心自己职责，service 不知道有 HTTP，schema 不知道有 DB——这是严格的关注点分离。"

### Q2：为什么 UserRead 不含 password_hash？

> "白名单设计——UserRead 只定义要返回的字段，敏感字段（password_hash）自动不返回。比黑名单（手动删字段）安全 10 倍：加新敏感字段时 ORM 加就好，不在 UserRead 加就自动不返回。架构层杜绝'忘记删敏感字段'的 bug。"

### Q3：业务异常怎么自动映射到 HTTP 状态码？

> "service 抛业务异常（UsernameExistsError），路由层用 `@app.exception_handler` 注册映射——UsernameExistsError → 409、EmailExistsError → 409、FitForgeException 基类 → 400。3 层兜底：具体异常 → 业务基类 → Exception。service 不知道 HTTP 存在，业务可复用（CLI/脚本/队列都直接调 service.register()）。"

### Q4：并发注册怎么处理？

> "应用层 99% 拦截（service 查重），DB 层 1% 兜底（UNIQUE 约束）。两个请求同时通过应用层查重时，DB UNIQUE 约束拒绝其中一个，抛 IntegrityError → handler 映射 409。纵深防御：应用层 + DB 层双保险。"

### Q5：422 vs 409 区别？

> "422 是 Pydantic 自动校验失败（请求格式错，比如密码无字母），客户端修输入。409 是数据冲突（用户名被占），用户改用户名。500 是后端 bug。422 = 用户输入问题，409 = 业务规则限制，500 = 后端代码 bug——三层语义清晰。"

---

## 7. 踩坑清单

| 坑 | 现象 | 解法 |
|----|------|------|
| service 抛 HTTPException | service 依赖 FastAPI | 自定义业务异常体系 + handler |
| 路由层手写 try/except | 业务代码有胶水 | add_exception_handler 注册 |
| 响应体含 password_hash | 敏感字段泄漏 | UserRead 不定义（白名单）|
| 黑名单过滤字段 | 加新字段要改 2 处 | 白名单（UserRead 只定义要返回的）|
| 校验失败返回 400 | 跟 FastAPI 默认 422 不一致 | 让 Pydantic 自动 422（不要 try/except） |
| 没 DB 兜底 | 并发注册 2 个通过 | UNIQUE 约束 + IntegrityError handler |

---

## 8. 关联文档

- spec 文档：`docs/superpowers/specs/2026-07-06-auth-register-design.md`
- plan 文档：`docs/superpowers/plans/2026-07-06-auth-register-plan.md`
- 路由层沉淀：`tech_notes/2026-07-06-fastapi-route-layer.md`
- Pydantic 沉淀：`tech_notes/2026-07-06-pydantic-v2-schema.md`
- 异常体系沉淀：`tech_notes/2026-07-06-business-exceptions.md`
- 部署记录：`tech_notes/2026-08-13-server-deploy-record.md`

---

**沉淀状态**：✅ 用户于 2026-07-06 批准落盘