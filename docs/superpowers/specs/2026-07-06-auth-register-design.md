# POST /auth/register 设计文档

> **日期**：2026-07-06（周三）
> **作者**：LHR6666（与 Claude Code brainstorming 产出）
> **状态**：✅ 用户已批准 v1（待 user review of written spec）
> **关联决策**：D4（SQLAlchemy 异步）、D5（PyJWT）、D6（Argon2id）、D9（Alembic）、D11（pydantic-settings）、D17（schema 蓝图）、D19（service 重型 + 业务异常体系 — **本 spec 通过后落盘到 project_progress.md**）

---

## 1. 背景与目标

### 1.1 业务目标

FitForge MVP 第一个业务端点：用户注册。支撑后续 `/auth/login`、目标管理、身体数据录入等所有需要登录态的功能。

### 1.2 设计目标

- ✅ 严格分层（路由 / service / model / schema 各司其职）
- ✅ 业务可复用（service 层不依赖 FastAPI，CLI/脚本/队列可直接调）**“Service 层不依赖 FastAPI”** = **“厨师不需要服务员也能炒菜”**。**好处**：这套注册逻辑，不仅网页能用，以后写自动脚本、做后台任务、或者换个框架，这套核心代码**一行都不用改**，直接拿来用。
- ✅ 安全第一（Argon2id 密码哈希、email/username 唯一性双层防御）
- ✅ 错误清晰（业务异常体系 + 状态码语义化）
- ✅ 演进友好（保留 5.x 周 DDD 三层升级路径）

### 1.3 MVP 范围

- ✅ 支持：注册（username + email + password + 可选 nickname）
- ❌ 不支持：邮箱验证、找回密码、第三方登录、注册即登录返回 token

---

## 2. 6 决策汇总（来自 brainstorming Q1-Q6）


| #   | 决策              | 选项                                                                        | 理由                          |
| --- | --------------- | ------------------------------------------------------------------------- | --------------------------- |
| Q1  | service 层职责边界   | **重型 service**（接 Pydantic schema、返回 ORM、抛业务异常）                            | 业务可复用、面试可讲"分层 + 异常映射"       |
| Q2  | 错误处理            | **业务异常体系**（`UsernameExistsError` 等，路由层注册 `exception_handler` 映射 HTTP 状态码） | service 不知道 HTTP、纯业务可测      |
| Q3  | session 注入      | `**async generator + Depends`**（`get_db()` yield session，try/finally 关闭）  | FastAPI 官方推荐、面试必讲           |
| Q4  | Pydantic schema | **2 个 schema**（`UserCreate` 请求 + `UserRead` 响应）                           | YAGNI、避免 password_hash 泄漏   |
| Q5  | 密码强度            | **中等**（`min_length=8` + 字母数字混合）                                           | 拦典型弱密码、代码适中                 |
| Q6  | email 字段        | **强制必填**                                                                  | 跟 D17 UNIQUE 约束一致、为未来找回密码铺路 |


---

## 3. 整体架构

```
Client ──POST /auth/register──▶ api/auth.py (路由层)
                                  │ ① 解析 body (Pydantic 自动校验)
                                  │ ② 调 service.register()
                                  │ ③ ORM → UserRead 转换
                                  │ ④ 注册 exception_handler
                                  ▼
                              services/auth_service.py (业务层)
                                  │ ⑤ 校验密码 (Pydantic 已做)
                                  │ ⑥ 查重 (username/email)
                                  │ ⑦ hash 密码 (Argon2id cost=12)
                                  │ ⑧ create User + flush + commit
                                  │ ⑨ 抛业务异常
                                  ▼
                              core/db.py (基础设施)
                                  │ ⑩ AsyncSession 注入
                                  ▼
                              MySQL.fitforge.users
```

**核心架构原则**：

- **路由层**：HTTP 适配（解析 body、调 service、ORM → DTO 转换、注册异常映射）
- **业务层**：纯业务（查重、哈希、写库），不知道 FastAPI 存在
- **基础设施层**：`core/db.py` / `core/security.py` / `core/exceptions.py`

---

## 4. 组件清单

### 4.1 新增/修改文件


| 文件                                                 | 状态           | 职责                                                                                              |
| -------------------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------- |
| `core/config.py`                                   | 新增           | pydantic-settings 读 .env（DATABASE_URL 等）                                                        |
| `core/db.py`                                       | 新增           | SQLAlchemy 2.0 异步 engine + `get_db()` async generator                                           |
| `core/security.py`                                 | 新增           | Argon2id `hash_password()` / `verify_password()`                                                |
| `core/exceptions.py`                               | 新增           | 业务异常类（`UsernameExistsError` / `EmailExistsError`）                                               |
| `models/__init__.py`                               | 新增           | 导出 `Base` + 3 个 model                                                                           |
| `models/user.py`                                   | 替换占位         | `User` ORM class                                                                                |
| `models/user_goal.py`                              | 替换占位         | `UserGoal` ORM class                                                                            |
| `models/body_measurement.py`                       | 替换占位         | `BodyMeasurement` ORM class                                                                     |
| `schemas/user.py`                                  | 替换占位         | `UserCreate` + `UserRead`                                                                       |
| `services/auth_service.py`                         | 替换占位         | `register(db, user_create) -> User`                                                             |
| `api/auth.py`                                      | 替换占位         | POST `/auth/register`                                                                           |
| `api/exception_handlers.py`                        | 新增           | exception_handler 注册函数                                                                          |
| `main.py`                                          | 修改           | `include_router(auth.router)` + `add_exception_handler(...)`                                    |
| `.env`                                             | 新增           | `DATABASE_URL` 等配置                                                                              |
| `.env.example`                                     | 修改           | 补 `DATABASE_URL` 示例                                                                             |
| `requirements.txt`                                 | 修改           | + `alembic` `asyncmy` `sqlalchemy[asyncio]` `passlib[argon2]` `argon2-cffi` `pydantic-settings` |
| `alembic.ini`                                      | 新增           | alembic 配置                                                                                      |
| `alembic/env.py`                                   | 新增           | 配 `DATABASE_URL` + 引入 `models`                                                                  |
| `alembic/versions/xxx_create_users.py`             | autogenerate | 第 1 个 migration                                                                                 |
| `alembic/versions/xxx_create_user_goals.py`        | autogenerate | 第 2 个 migration                                                                                 |
| `alembic/versions/xxx_create_body_measurements.py` | autogenerate | 第 3 个 migration                                                                                 |
| `tests/test_auth.py`                               | 新增           | 端到端测试                                                                                           |


### 4.2 各文件关键代码骨架

#### `core/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+asyncmy://fitforge:fitforge_dev_password_2026@localhost:3306/fitforge"
    JWT_PRIVATE_KEY_PATH: str = "./keys/private.pem"
    JWT_PUBLIC_KEY_PATH: str = "./keys/public.pem"
    JWT_ALGORITHM: str = "RS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

#### `core/db.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from core.config import settings
from models import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,  # MVP 阶段开，方便看 SQL
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

#### `core/security.py`

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

#### `core/exceptions.py`

```python
class FitForgeException(Exception):
    """FitForge 业务异常基类"""
    pass

class UsernameExistsError(FitForgeException):
    """用户名已被占用"""
    pass

class EmailExistsError(FitForgeException):
    """邮箱已被注册"""
    pass
```

#### `models/user.py`

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    goals = relationship("UserGoal", back_populates="user", cascade="all, delete-orphan")
    measurements = relationship("BodyMeasurement", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"
```

#### `models/user_goal.py` / `models/body_measurement.py`

按 D17 蓝图 §3.2 / §3.3 完整实现（详见 `tech_notes/2026-07-02-mvp-blueprint-design.md`）。

#### `schemas/user.py`

```python
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("password")
    @classmethod
    def password_must_contain_letter_and_digit(cls, v: str) -> str:
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v


class UserRead(BaseModel):
    id: int
    username: str
    nickname: str | None = None

    model_config = {"from_attributes": True}  # 允许从 ORM 对象构造
```

#### `services/auth_service.py`

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.security import hash_password
from core.exceptions import UsernameExistsError, EmailExistsError
from models.user import User
from schemas.user import UserCreate

async def register(db: AsyncSession, user_create: UserCreate) -> User:
    """注册新用户。返回 ORM 对象（路由层负责转 DTO）。

    业务规则：
    - username 全局唯一
    - email 全局唯一
    - 密码用 Argon2id 哈希（cost=12）
    """
    # 查重
    existing = await db.execute(select(User).where(User.username == user_create.username))
    if existing.scalar_one_or_none():
        raise UsernameExistsError(f"用户名 '{user_create.username}' 已被占用")

    existing = await db.execute(select(User).where(User.email == user_create.email))
    if existing.scalar_one_or_none():
        raise EmailExistsError(f"邮箱 '{user_create.email}' 已被注册")

    # 创建
    user = User(
        username=user_create.username,
        email=user_create.email,
        password_hash=hash_password(user_create.password),
        nickname=user_create.nickname,
    )
    db.add(user)
    await db.flush()  # 取 id
    await db.commit()
    return user
```

#### `api/auth.py`

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from schemas.user import UserCreate, UserRead
from services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await auth_service.register(db, user_create)
    return UserRead.model_validate(user)
```

#### `api/exception_handlers.py`

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from core.exceptions import UsernameExistsError, EmailExistsError, FitForgeException

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UsernameExistsError)
    async def username_exists_handler(request: Request, exc: UsernameExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(EmailExistsError)
    async def email_exists_handler(request: Request, exc: EmailExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        # DB 层兜底（应对并发注册同 username/email）
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "数据冲突，可能是 username 或 email 已被占用"},
        )

    @app.exception_handler(FitForgeException)
    async def fitforge_exception_handler(request: Request, exc: FitForgeException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )
```

#### `main.py`（修改部分）

```python
from fastapi import FastAPI
from api.auth import router as auth_router
from api.exception_handlers import register_exception_handlers
from models import Base
from core.db import engine

app = FastAPI(title="FitForge API", version="0.1.0")

register_exception_handlers(app)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {"message": "FitForge API", "version": "0.1.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

## 5. 数据流（10 步详解）

1. **客户端** `POST /auth/register` + JSON body
2. **FastAPI 解析 body** → 自动用 `UserCreate` Pydantic 校验
  - 失败 → 自动返回 **422** + 详细错误
  - 字段：username 3-50 字符、`^[a-zA-Z0-9_]+$`、email `EmailStr`、password `min_length=8` + 字母数字 validator
3. **路由函数** `register(user_create: UserCreate, db: AsyncSession = Depends(get_db))` 被调用
4. **路由层** 调 `await auth_service.register(db, user_create)`
5. **service 层** 业务逻辑：
  - `SELECT * FROM users WHERE username = ?` → 找到抛 `UsernameExistsError`
  - `SELECT * FROM users WHERE email = ?` → 找到抛 `EmailExistsError`
  - `pwd_hash = security.hash_password(password)`（Argon2id cost=12）
  - `user = User(username=..., email=..., password_hash=pwd_hash, nickname=...)`
  - `db.add(user)` + `db.flush()`（取 id，不 commit）+ `db.commit()`（持久化）
  - 返回 `user` (ORM 对象)
6. **路由层** 收到 ORM 对象 → `UserRead.model_validate(user)` 转换
7. **FastAPI 序列化** → JSON `{"id": 1, "username": "alice", "nickname": null}`
8. **HTTP 响应** **201 Created** + body
9. **客户端** 拿到响应，记录用户

**session 生命周期**：

- 请求开始：`get_db()` yield 新 session
- 请求结束（成功/异常）：`finally` 关闭 session
- 异常时：先 `rollback()` 再关闭



通俗说法：

### **第一阶段：前台接待（第 1-3 步）**

**角色：客户端 & FastAPI 路由层**

这个阶段的核心是**“验票”**——看用户带来的数据合不合规。

1. **客户端发请求**：用户在 App/网页上点“注册”，浏览器发了一个 `POST` 请求，包里装着 JSON 数据（比如 `{"username": "alice", ...}`）。
2. **FastAPI 自动校验**：
  - FastAPI 就像门口的保安。它拿着 `UserCreate` 这个“入场标准”去比对数据。
  - **如果不合格**（比如密码只有 3 位，或者邮箱格式不对）：保安直接拦下，扔出一张 **422 错误单**（Unprocessable Entity），流程直接结束，根本不进后厨。
  - **如果合格**：保安把数据打包成一个 Python 对象（`user_create`），放行。
3. **路由函数接手**：
  - 这时，代码里的 `register` 函数被唤醒。
  - 关键动作 `Depends(get_db)`：这就是**依赖注入**。函数大喊一声“我要个数据库连接！”，FastAPI 就像服务员一样，立马递过来一个连接对象 `db`。
  - 路由层不做业务，它只当**传声筒**：拿着数据和连接，喊一声：“后厨（Service 层），开工了！”

### **第二阶段：后厨加工（第 4-5 步）**

**角色：Service 业务层**

这是整个流程**最核心、最复杂**的部分。Service 层拿到“原材料”后，开始精加工。

1. **Service 层的业务逻辑**（拆解为 5 个小动作）：
  - **① 查重**：
    - 先去仓库看一眼：`SELECT * FROM users WHERE username = ?`。
    - 如果发现有同名用户，直接**抛异常**（`UsernameExistsError`）。这就像大厨发现食材坏了，直接把锅扔了，不干了。这个异常会被最外层的“异常处理器”捕获，变成 409 错误返回给用户。
  - **② 加密**：
    - 这是安全的关键。用户的明文密码（如 `123456`）绝不能直接存。
    - Service 调用 `security.hash_password`，用 Argon2id 算法把密码变成一串乱码（如 `$argon2id$v=19...`）。
  - **③ 建模**：
    - 创建一个 `User` 对象（ORM 对象），把用户名、加密后的密码塞进去。这就像把做好的菜装进盘子。
  - **④ 入库准备**：
    - `db.add(user)`：把盘子端到仓库门口。
    - `db.flush()`：**这是个关键动作**。它相当于“预提交”。它让数据库生成了 ID（自增主键），但还没真正写入硬盘。这样做是为了拿到 ID，万一后续还有操作，可以直接用。
    - `db.commit()`：**正式提交**。这一下，数据才真正写进了硬盘。
  - **⑤ 返回**：把存好的 `user` 对象（这时候它已经有 ID 了）交还给路由层。

### **第三阶段：安全交付（第 6-9 步）**

**角色：路由层 & Pydantic Schema**

1. **ORM 转 DTO（关键的安全过滤）**：
  - Service 交还的是 `User` 对象（ORM），里面**包含**密码哈希。
  - 路由层用 `UserRead.model_validate(user)` 进行转换。
  - **神奇的一幕发生了**：`UserRead` 这个模子里**根本没有定义** `password` 字段。
  - 所以，转换出来的结果里，密码字段自动消失了。这就是**“白名单机制”**——我没写的字段，绝对不返回。

7-9. **打包发货**：  
* FastAPI 把 `UserRead` 对象变成 JSON 字符串。  
* 包装成 HTTP 响应，状态码设为 **201**（Created）。  
* 发回给客户端。

### **第四阶段：清洁收尾**

**这不在主流程 10 步里，但在后台默默运行。**

- `get_db()` **的魔法**：
  - 你在路由函数里用的 `db` 对象，其实是一个“生成器”。
  - **请求开始时**：`yield session` 给你用。
  - **请求结束后**：不管你是成功存盘了，还是中间报错了，代码都会进入 `finally` 块。
  - **异常处理**：如果中间报错了（比如数据库崩了），`finally` 会执行 `session.rollback()`（回滚），就像 Word 文档没保存就撤销一样，保证数据库里不会留下烂尾数据。最后 `session.close()` 关闭连接，释放资源。

### **总结一张图**

你可以把这个流程想象成一条流水线：

1. **进料口**（路由层）：检查原材料格式（Pydantic），不合格直接踢出去（422）。
2. **加工台**（Service 层）：
  - 查库存（查重）
  - 秘制配方（密码加密）
  - 半成品组装（ORM 对象）
3. **仓库**（数据库）：入库落锁。
4. **出料口**（路由层）：贴标签（过滤敏感信息），打包发货（JSON 201）。

---

## 6. 错误处理（异常 → 状态码映射）


| 异常                         | 状态码 | 响应体                            | 触发场景                         |
| -------------------------- | --- | ------------------------------ | ---------------------------- |
| Pydantic `ValidationError` | 422 | FastAPI 默认                     | username/email/password 格式错  |
| `UsernameExistsError`      | 409 | `{"detail": "用户名 'xxx' 已被占用"}` | service 层 username 查重失败      |
| `EmailExistsError`         | 409 | `{"detail": "邮箱 'xxx' 已被注册"}`  | service 层 email 查重失败         |
| `IntegrityError`           | 409 | `{"detail": "数据冲突..."}`        | DB 层兜底（并发注册同 username/email） |
| `FitForgeException`（其他）    | 400 | `{"detail": str(exc)}`         | 其他业务异常                       |
| `Exception`（未捕获）           | 500 | FastAPI 默认                     | 系统错误                         |


**双层防御**：

- 应用层（service 查重）：99% 情况拦截，给出明确错误信息
- DB 层（UNIQUE 约束）：1% 并发情况兜底，避免数据不一致

---

## 7. 测试策略


| 层级       | 工具                                   | 覆盖                                                     |
| -------- | ------------------------------------ | ------------------------------------------------------ |
| 单元       | `pytest` + `pytest-asyncio`          | `core/security.py` hash/verify 正确性                     |
| 集成       | `pytest` + `httpx.AsyncClient`       | `/auth/register` 端到端：成功 / username 重复 / email 重复 / 弱密码 |
| DB 验证    | `alembic upgrade head` + `mysql` CLI | 3 张表创建成功、CASCADE 生效                                    |
| 手工 smoke | `curl`                               | 注册端到端                                                  |


**MVP 测试用例清单**：

```python
# tests/test_auth.py

import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_register_success():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "Password123",
            "nickname": "Alice"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "alice"
        assert "id" in data
        assert "password" not in data  # 关键：不能泄漏 password
        assert "password_hash" not in data

@pytest.mark.asyncio
async def test_register_duplicate_username():
    # 先注册一个
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/auth/register", json={
            "username": "bob", "email": "bob@example.com", "password": "Password123"
        })
        # 再注册同 username
        resp = await client.post("/auth/register", json={
            "username": "bob", "email": "bob2@example.com", "password": "Password123"
        })
        assert resp.status_code == 409

@pytest.mark.asyncio
async def test_register_weak_password():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/auth/register", json={
            "username": "charlie", "email": "charlie@example.com", "password": "12345678"
        })
        assert resp.status_code == 422  # 纯数字，无字母
```

---

## 8. 风险点 + 防范


| 风险                                  | 影响            | 防范策略                                                               | 验证手段                                      |
| ----------------------------------- | ------------- | ------------------------------------------------------------------ | ----------------------------------------- |
| **并发注册同 username 致 IntegrityError** | 数据不一致         | 应用层先查重 + DB 层 UNIQUE 约束兜底                                          | 并发测试：开 10 个线程同时注册                         |
| **password_hash 字段泄漏到响应**           | 严重安全事故        | 路由层强制 `UserRead.model_validate()` + UserRead 不定义 password_hash     | 单元测试断言 `password_hash not in resp.json()` |
| **Alembic autogenerate 漏改 ENUM 值**  | 线上 enum 变更失败  | 人工 review 每个 migration 文件、特别检查 enum 列表                             | 每次 migration diff review                  |
| **明文密码误传日志**                        | 严重安全事故        | service 层只在内存处理 password、绝不打 logger、ORM 字段 `password_hash` 不打 repr | grep 全文无 password 明文                      |
| **D17 schema 与 ORM 不一致**            | 上线后 schema 偏差 | ORM 写完立刻 `alembic upgrade head` 在本地建库 + `mysql -e "DESC users"` 对比 | D17 蓝图 §3.1 字段表与 DB DESC 输出对比             |
| **asyncmy 连接池耗尽**                   | 高并发下雪崩        | 配 `pool_size=10, max_overflow=20` + `pool_pre_ping=True`           | 压测 100 并发                                 |


---

## 9. 备选方案（如果未来升级）

### 9.1 方案 B：DDD 三层架构

- **升级路径**：service 接 dataclass DTO、DB 操作抽到 `repository/user_repo.py`
- **触发条件**：第 5 周做 `/auth/login` 时若 service 逻辑超 200 行
- **决策权**：留到那时再 brainstorm

### 9.2 方案 C：注册即返回 token

- **升级路径**：注册成功后 service 调 `security.create_access_token(user.id)`，响应体增加 `access_token` / `token_type`
- **触发条件**：MVP 跑通后想简化前端流程
- **风险**：注册 = 隐式登录，需谨慎

---

## 10. 实施 TODO（writing-plans 阶段细化）

```
大块 1：环境 + DB 连接
  □ pip install alembic asyncmy sqlalchemy[asyncio] passlib[argon2] argon2-cffi pydantic-settings
  □ 更新 requirements.txt
  □ 写 core/config.py（pydantic-settings）
  □ 写 core/db.py（异步 engine + get_db）
  □ 创建 .env + 修改 .env.example
  □ 本地起 MySQL（或用服务器 fitforge 库）
  □ 跑通 await db.execute(text("SELECT 1"))

大块 2：3 个 model 文件
  □ 写 models/__init__.py（导出 Base）
  □ 写 models/user.py（按 D17 §3.1）
  □ 写 models/user_goal.py（按 D17 §3.2）
  □ 写 models/body_measurement.py（按 D17 §3.3）

大块 3：Alembic 初始化 + 3 次迁移
  □ alembic init alembic
  □ 改 alembic.ini + alembic/env.py（DATABASE_URL + target_metadata = Base.metadata）
  □ alembic revision --autogenerate -m "create users table"
  □ review SQL（确认 UNIQUE、ENUM、复合索引）
  □ alembic upgrade head
  □ 同理 user_goals + body_measurements（3 次迁移）
  □ mysql -e "DESC users" 验证

大块 4：Pydantic schema
  □ 写 core/security.py（Argon2id hash + verify）
  □ 写 core/exceptions.py（FitForgeException + 子类）
  □ 写 schemas/user.py（UserCreate + UserRead）

大块 5：/auth/register 路由
  □ 写 services/auth_service.py（register 函数）
  □ 写 api/auth.py（POST /auth/register）
  □ 写 api/exception_handlers.py
  □ 修改 main.py（include_router + register_exception_handlers）

大块 6：测试 + 收尾
  □ 写 tests/test_auth.py（4 个用例）
  □ 跑 pytest 全过
  □ curl 端到端 smoke
  □ 同步到服务器（scp 或 git push + pull）
  □ 服务器 alembic upgrade head
  □ 服务器 curl /auth/register 验证
  □ git add + commit（Conventional Commits）
  □ 写 tech_notes/2026-07-06-fastapi-register-flow.md（核心原理 + 面试话术）
  □ 追加 D19 到 project_progress.md「重大决策记录」
```

---

## 11. 面试话术（预演）

### Q1：为什么 service 层抛异常而不是返回错误码？

> "我用业务异常体系而非 Result 模式，因为：① Python 异常原生支持 try/except，调用者代码最简洁；② 业务异常与 HTTP 异常解耦——service 不知道有 HTTP，所以业务可复用（CLI/脚本/队列都直接调 service.register()）；③ FastAPI 的 `add_exception_handler` 让我一处定义映射，N 个端点受益。"

### Q2：为什么用 Depends(get_db) 而不是全局 session？

> "我用 FastAPI 官方的 async generator + Depends 模式，因为：① session 生命周期与 HTTP 请求绑定（请求开始开、结束关），避免泄漏；② 每个请求独立 session，天然隔离、并发安全；③ 单元测试时可 override Depends 注入 mock session，比全局单例好测 10 倍。"

### Q3：password_hash 怎么防止泄漏？

> "三层防御：① Pydantic UserRead 不定义 password_hash 字段；② 路由层强制 `UserRead.model_validate(orm_user)` 而非 `orm_user.dict()`；③ 单元测试断言 `assert 'password_hash' not in resp.json()`。这个'白名单 vs 黑名单'的思维——'不显式声明就不返回'比'努力过滤敏感字段'更安全。"

### Q4：为什么 email 必填？

> "D17 蓝图里 email 已是 UNIQUE 约束，强制必填跟 schema 一致；虽然 MVP 阶段不做找回密码，但 schema 不动是'未来钩子'——等真做找回密码时零成本启动。"

### Q5：Argon2id vs bcrypt？

> "Argon2id 是 OWASP 2023+ 推荐的 PHC 算法，相比 bcrypt 抗 GPU/ASIC 攻击更强——因为它是 memory-hard（内存硬性）的，硬件加速成本高。"

---

## 12. 审批与变更记录


| 日期         | 版本  | 变更                                | 审批人               |
| ---------- | --- | --------------------------------- | ----------------- |
| 2026-07-06 | v1  | 初稿：6 决策 + 完整架构 + 数据流 + 错误处理 + 风险点 | LHR6666（待 review） |


---

**审批状态**：⏳ 待 user review