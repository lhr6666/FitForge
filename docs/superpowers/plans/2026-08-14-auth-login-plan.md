# /auth/login + refresh + logout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 /auth/login + refresh + logout + get_current_user 中间件 + JWT 双 token 机制（access 30min + refresh 14day + rotate）。

**Architecture:** 严格分层（api/ 路由 + services/ 业务 + models/ ORM + schemas/ Pydantic + core/ 配置）。复用 /auth/register 的 Q1-Q6 决策（重型 service、业务异常、Depends 注入、2 schema 隔离密码、中等密码、email 必填）。双 token + refresh rotate 机制（防重放）：每次 refresh 作废旧 refresh + 签发新 refresh。

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 (asyncmy) / MySQL 8.0 / Pydantic v2 / PyJWT (RS256) / passlib[argon2]

**Spec:** `docs/superpowers/specs/2026-08-14-auth-login-design.md`（commit `1d81d0c`）

## Global Constraints

- Python 3.10+（用 `from __future__ import annotations` 和 PEP 604 `|` 语法）
- 数据库：本地 Docker MySQL（端口 3307，密码 lhr076200）+ 服务器 MySQL（端口 3306，密码 lhr076200）
- 时间戳：所有 DateTime 字段一律 UTC（用 `datetime.now(timezone.utc)`）
- JWT 配置：JWT_PRIVATE_KEY_PATH=./keys/private.pem / JWT_PUBLIC_KEY_PATH=./keys/public.pem / JWT_ALGORITHM=RS256 / JWT_EXPIRE_MINUTES=1440（已在 core/config.py）
- 业务异常体系：所有业务异常继承 FitForgeException 基类（Q2 决策）
- 路由层不写业务逻辑（Q1 决策）
- service 层不知道有 FastAPI（Q1 决策）
- ORM 不返回密码字段（Q4 决策）
- 测试：pytest + pytest-asyncio + httpx
- Commit 规范：Conventional Commits（feat/fix/docs/refactor/test/chore）
- 依赖管理：pip install 同步更新 requirements.txt
- RSA 密钥对：本地用 `openssl genrsa -out keys/private.pem 2048`，存 keys/ 目录（不入 Git，.gitignore 已有）
- 完整产出：4 端点 + 1 中间件 + 1 新表 + 4 异常 + 10 commit（按 §11）

---

## Task 1: core/security.py 加 JWT 函数（create/decode + 密钥加载）

**Files:**
- Modify: `core/security.py`（已有 passlib 代码，末尾追加）
- Modify: `requirements.txt`（确保 PyJWT 已装）

**Interfaces:**
- Consumes: `core.config.settings`（JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH / JWT_ALGORITHM）
- Produces:
  - `create_access_token(user_id: int) -> str`（签发 30 分钟 access token）
  - `create_refresh_token(user_id: int) -> tuple[str, str]`（签发 14 天 refresh token + 返回 jti）
  - `decode_access_token(token: str) -> dict[str, Any]`（解码 + 验证，失败抛 InvalidTokenError）
  - `decode_refresh_token(token: str) -> dict[str, Any]`（同上，专用于 refresh）

- [ ] **Step 1: 检查 PyJWT 已装**

```bash
pip show PyJWT
# 预期：Version: 2.x.x
```

未装则：

```bash
pip install PyJWT[crypto]==2.10.1
```

- [ ] **Step 2: 生成 RSA 密钥对（本地 + 服务器）**

```bash
# 本地（Git Bash）
mkdir -p keys
cd keys
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
# icacls 权限（D18 决策）
powershell -Command 'icacls "D:\My Agnet\my_coding_projects\Intelligent_training_management_platform\keys\private.pem" /inheritance:r /grant:r "$env:USERNAME:(R)"'
cd ..
```

服务器端同样（部署时）。

- [ ] **Step 3: 在 core/security.py 末尾追加 JWT 函数**

追加代码（保留原 passlib 部分）：

```python
# ===== JWT 密钥加载（启动时一次） =====
import jwt
from datetime import datetime, timedelta, timezone
from typing import Any
from core.exceptions import InvalidTokenError

_PRIVATE_KEY: str = ""
_PUBLIC_KEY: str = ""


def _load_keys() -> None:
    """启动时加载 RSA 密钥对（仅一次）。"""
    global _PRIVATE_KEY, _PUBLIC_KEY
    with open(settings.JWT_PRIVATE_KEY_PATH) as f:
        _PRIVATE_KEY = f.read()
    with open(settings.JWT_PUBLIC_KEY_PATH) as f:
        _PUBLIC_KEY = f.read()


_load_keys()


# ===== Token 寿命常量 =====
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 14


def create_access_token(user_id: int) -> str:
    """签发 access token（30 分钟）。

    Payload: {sub: user_id, iat, exp, type: "access"}
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """签发 refresh token（14 天）+ 返回 jti。

    Returns: (token, jti)
    Payload: {sub, jti, iat, exp, type: "refresh"}
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
        "type": "refresh",
    }
    token = jwt.encode(payload, _PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_access_token(token: str) -> dict[str, Any]:
    """解码 + 验证 access token。失败抛 InvalidTokenError。"""
    try:
        payload = jwt.decode(token, _PUBLIC_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("token 已过期")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("token 无效")
    if payload.get("type") != "access":
        raise InvalidTokenError("token 类型错误（不是 access）")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """解码 + 验证 refresh token。失败抛 InvalidTokenError。"""
    try:
        payload = jwt.decode(token, _PUBLIC_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("refresh token 已过期")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("refresh token 无效")
    if payload.get("type") != "refresh":
        raise InvalidTokenError("token 类型错误（不是 refresh）")
    return payload
```

顶部 import 也要加上（已有 `from core.config import settings` 假设，否则添加）：

```python
import uuid
from core.config import settings
```

- [ ] **Step 4: 验证 import + 4 个函数可调用**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
from core.security import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token
t1 = create_access_token(1)
t2, jti = create_refresh_token(1)
print('access:', t1[:50], '...')
print('refresh jti:', jti)
p1 = decode_access_token(t1)
p2 = decode_refresh_token(t2)
print('decoded sub:', p1['sub'], '/', p2['sub'])
print('OK: 4 functions work')
"
```

预期：`access: eyJ...` + `refresh jti: <uuid>` + `decoded sub: 1 / 1` + `OK`

- [ ] **Step 5: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add core/security.py requirements.txt && git commit -m "feat(security): add JWT create/decode functions (RS256)

D5 decision: PyJWT
D7 decision: RS256 + RSA 2048 keys

4 functions:
- create_access_token(user_id): 30 min lifetime
- create_refresh_token(user_id): 14 day lifetime + jti
- decode_access_token(token): verify signature + exp + type
- decode_refresh_token(token): same + type=refresh check

Key loading at startup (load_keys() once)
InvalidTokenError raised on decode failure"
```

---

## Task 2: core/exceptions.py 加 2 个新异常

**Files:**
- Modify: `core/exceptions.py`（已有 FitForgeException 基类 + UsernameExistsError + EmailExistsError）

**Interfaces:**
- Consumes: 现有 `FitForgeException` 基类
- Produces:
  - `InvalidCredentialsError(FitForgeException)`（登录失败）
  - `InvalidTokenError(FitForgeException)`（token 无效/过期/类型错）

- [ ] **Step 1: 追加 2 个异常类**

在 `core/exceptions.py` 文件末尾追加：

```python
class InvalidCredentialsError(FitForgeException):
    """登录凭证错误（HTTP 401）。

    触发场景：
        - email 不存在
        - password 错误

    注意：两个场景返回**统一消息**（防枚举攻击）
    """
    pass


class InvalidTokenError(FitForgeException):
    """JWT token 无效（HTTP 401）。

    触发场景：
        - token 签名错
        - token 已过期
        - token 类型错（拿 refresh 当 access 用）
        - token 被撤销（refresh 表 revoked=true）
    """
    pass
```

- [ ] **Step 2: 验证 import**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
from core.exceptions import FitForgeException, InvalidCredentialsError, InvalidTokenError
e1 = InvalidCredentialsError('test')
e2 = InvalidTokenError('test')
assert isinstance(e1, FitForgeException)
assert isinstance(e2, FitForgeException)
print('OK: 2 new exceptions inherit from FitForgeException')
"
```

预期：`OK: 2 new exceptions...`

- [ ] **Step 3: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add core/exceptions.py && git commit -m "feat(exceptions): add InvalidCredentialsError + InvalidTokenError

Q2 decision: business exception system

2 new exceptions:
- InvalidCredentialsError: login failed (unified msg anti-enumeration)
- InvalidTokenError: JWT invalid/expired/wrong-type/revoked

Both inherit FitForgeException -> 401 in handler (next task)"
```

---

## Task 3: models/user.py 加 RefreshToken 模型 + User 关系

**Files:**
- Modify: `models/user.py`（已有 User ORM）
- Modify: `models/__init__.py`（确保 RefreshToken 被 import + 注册到 Base.metadata）

**Interfaces:**
- Consumes: 现有 `Base` + `User`
- Produces:
  - `RefreshToken(Base)` 类
  - `User.refresh_tokens` relationship

- [ ] **Step 1: 在 models/user.py 末尾追加 RefreshToken**

```python
class RefreshToken(Base):
    """RefreshToken ORM 模型。

    存储每个 refresh token 的 jti + 过期时间 + 撤销状态。
    每次 login/refresh 写一行；logout/rotate 标记 revoked=True。
    """

    __tablename__ = "refresh_tokens"

    # ===== 主键 =====
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ===== 外键（D29: DB 存 jti + revoke）=====
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ===== 业务字段 =====
    jti = Column(String(36), unique=True, nullable=False, index=True)  # UUID4 字符串
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    # ===== 时间戳（D17-g 全表统一）=====
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ===== 关系 =====
    user = relationship("User", back_populates="refresh_tokens")

    # ===== 复合索引（D17-b 原则：跟随 WHERE 子句）=====
    __table_args__ = (
        Index("idx_refresh_tokens_user_active", "user_id", "revoked"),
    )
```

同时在 `User` 类加 `refresh_tokens` 关系（找到已有 `goals` 和 `measurements` 处）：

```python
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

- [ ] **Step 2: 验证模型注册到 Base.metadata**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
from models import Base, User, RefreshToken
tables = list(Base.metadata.tables.keys())
print(f'tables: {tables}')
assert 'refresh_tokens' in tables, 'refresh_tokens not registered'
rt = RefreshToken(user_id=1, jti='test-jti-123456789012345678901234', expires_at='2026-12-31')
print(f'refresh_token instance: {rt}')
print('OK: RefreshToken registered')
"
```

预期：`tables: ['users', 'user_goals', 'body_measurements', 'refresh_tokens']`

- [ ] **Step 3: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add models/user.py models/__init__.py && git commit -m "feat(models): add RefreshToken ORM with jti + revoked field

D29 decision: refresh token DB storage

Fields:
- jti: UUID4 string (unique, indexed)
- expires_at: DateTime (UTC)
- revoked: Boolean (default false)
- created_at: DateTime (UTC)

Foreign key: user_id -> users.id (CASCADE)
Compound index: (user_id, revoked) for active token lookup

User model: added refresh_tokens relationship (CASCADE delete-orphan)"
```

---

## Task 4: alembic autogenerate refresh_tokens 表

**Files:**
- Create: `alembic/versions/<hash>_add_refresh_tokens_table.py`（autogenerate 自动生成）

**Interfaces:**
- Consumes: `Base.metadata`（已有 RefreshToken 注册）
- Produces: `refresh_tokens` 表在 MySQL 中

- [ ] **Step 1: 启动本地 Docker MySQL（如未启动）**

```bash
docker ps --filter "name=fitforge-mysql" | grep -q "Up" || docker start fitforge-mysql
sleep 2
docker ps --filter "name=fitforge-mysql"
```

预期：`Up 3 seconds` 类似输出

- [ ] **Step 2: 跑 autogenerate**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && alembic revision --autogenerate -m "add refresh_tokens table"
```

预期输出：
```
INFO  [alembic.autogenerate.compare] Detected added table 'refresh_tokens'
Generating .../alembic/versions/<hash>_add_refresh_tokens_table.py ... done
```

- [ ] **Step 3: 人工 review 生成的 migration**

```bash
ls alembic/versions/*.py | sort -r | head -2
```

打开最新生成的文件，确认：
- ✅ `op.create_table('refresh_tokens', ...)` 含 jti/expires_at/revoked/created_at/user_id
- ✅ `op.create_index(op.f('ix_refresh_tokens_jti'), 'refresh_tokens', ['jti'], unique=True)`
- ✅ `op.create_index('idx_refresh_tokens_user_active', 'refresh_tokens', ['user_id', 'revoked'], unique=False)`
- ✅ `sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')`

- [ ] **Step 4: 跑 upgrade head**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && alembic upgrade head
```

预期：`Running upgrade  -> <hash>, add refresh_tokens table`

- [ ] **Step 5: pymysql 验证表结构**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
import pymysql
conn = pymysql.connect(host='localhost', port=3307, user='fitforge', password='lhr076200', database='fitforge')
cur = conn.cursor()
cur.execute('DESC refresh_tokens')
print('refresh_tokens columns:')
for row in cur.fetchall():
    print(f'  {row[0]:18} {row[1]:20}')
cur.execute('SHOW INDEX FROM refresh_tokens')
print('refresh_tokens indexes:', sorted(set(r[2] for r in cur.fetchall())))
conn.close()
print('OK: refresh_tokens table created')
"
```

预期：7 列 + 3 索引（jti/created_at 自动 + idx_user_active 复合）

- [ ] **Step 6: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add alembic/versions/ && git commit -m "feat(db): create refresh_tokens table via alembic migration

Fields: id / user_id (FK CASCADE) / jti (UUID unique) / expires_at / revoked / created_at
Indexes: PRIMARY / ix_refresh_tokens_jti (unique) / ix_refresh_tokens_user_id / idx_refresh_tokens_user_active (compound)

D29/D30 decision: DB storage + revoke field

alembic upgrade head verified: 7 columns + 3 indexes match D29 design"
```

---

## Task 5: schemas/user.py 加 3 个新 schema（Login/Refresh/Token）

**Files:**
- Modify: `schemas/user.py`（已有 UserCreate + UserRead）

**Interfaces:**
- Consumes: Pydantic v2
- Produces:
  - `LoginRequest(BaseModel)`（email + password）
  - `RefreshRequest(BaseModel)`（refresh_token）
  - `TokenResponse(BaseModel)`（access + refresh + token_type + expires_in）

- [ ] **Step 1: 在 schemas/user.py 末尾追加 3 个 schema**

```python
class LoginRequest(BaseModel):
    """登录请求体（email + password）。"""

    email: EmailStr = Field(description="邮箱（Q6 必填）")
    password: str = Field(min_length=8, max_length=128, description="明文密码（路由层转 service.verify_password）")


class RefreshRequest(BaseModel):
    """刷新 token 请求体（只用 refresh_token）。"""

    refresh_token: str = Field(
        min_length=10,
        description="14 天有效 refresh token（D28 双 token 机制）",
    )


class TokenResponse(BaseModel):
    """登录 / 刷新响应体（双 token + 元信息）。"""

    access_token: str = Field(description="Access token（30 分钟有效，Authorization Bearer 用）")
    refresh_token: str = Field(description="Refresh token（14 天有效，/auth/refresh 用）")
    token_type: str = Field(default="bearer", description="固定 'bearer'（OAuth 2.0 标准）")
    expires_in: int = Field(description="Access token 寿命（秒），默认 1800 = 30 分钟")
```

- [ ] **Step 2: 验证校验规则**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
from schemas.user import LoginRequest, RefreshRequest, TokenResponse

# Login 成功
u = LoginRequest(email='alice@example.com', password='Password123')
print(f'Login OK: {u.email}')

# Login 弱密码 → Pydantic 自动 422（service 不用管）
try:
    LoginRequest(email='alice@example.com', password='12345678')
    print('FAIL: weak password accepted')
except Exception as e:
    print(f'Login weak password rejected: {type(e).__name__}')

# Refresh 缺 refresh_token → Pydantic 自动 422
try:
    RefreshRequest()
    print('FAIL: missing refresh_token accepted')
except Exception as e:
    print(f'Refresh missing rejected: {type(e).__name__}')

# TokenResponse 默认值
t = TokenResponse(access_token='a', refresh_token='b', expires_in=1800)
print(f'TokenResponse default token_type: {t.token_type}')
print('OK: 3 new schemas work')
"
```

预期：3 个 schema 都正确校验

- [ ] **Step 3: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add schemas/user.py && git commit -m "feat(schemas): add LoginRequest + RefreshRequest + TokenResponse

3 new Pydantic schemas:
- LoginRequest: email (EmailStr) + password (min_length=8)
- RefreshRequest: refresh_token (min_length=10)
- TokenResponse: access_token + refresh_token + token_type=bearer + expires_in

Used by Task 6 (service) and Task 8 (router)"
```

---

## Task 6: services/auth_service.py 加 login + refresh_token + logout

**Files:**
- Modify: `services/auth_service.py`（已有 `register` 函数）

**Interfaces:**
- Consumes: Task 1 的 JWT 函数 + Task 3 的 RefreshToken 模型 + Task 5 的 3 schema
- Produces:
  - `async def login(db: AsyncSession, email: str, password: str) -> tuple[str, str, int]` 返回 (access, refresh, expires_in)
  - `async def refresh_token(db: AsyncSession, refresh_token: str) -> tuple[str, str, int]` rotate
  - `async def logout(db: AsyncSession, refresh_token: str) -> None` 幂等

- [ ] **Step 1: 在 auth_service.py 末尾追加 3 个函数**

追加代码（顶部 import 加）：

```python
# 顶部 import 新增
from datetime import datetime, timezone, timedelta
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from core.exceptions import InvalidCredentialsError, InvalidTokenError
from models.user import RefreshToken
```

```python
async def login(db: AsyncSession, email: str, password: str) -> tuple[str, str, int]:
    """验证 email + password → 签发 access + refresh。

    Returns: (access_token, refresh_token, expires_in_seconds)
    Raises:
        InvalidCredentialsError: 用户不存在 or 密码错（统一消息防枚举）
    """
    # 1. 查 user（按 email）
    from sqlalchemy import select
    user = (await db.execute(
        select(User).where(User.email == email)
    )).scalar_one_or_none()

    if not user:
        # 统一消息：不区分"用户不存在"和"密码错"
        raise InvalidCredentialsError("邮箱或密码错误")

    # 2. 验密码（Argon2id verify）
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("邮箱或密码错误")

    # 3. 签发 access + refresh
    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)

    # 4. refresh 写 DB（D29: jti 存 DB）
    expires_at = datetime.now(timezone.utc) + timedelta(days=14)
    db.add(RefreshToken(
        user_id=user.id,
        jti=jti,
        expires_at=expires_at,
    ))
    await db.commit()

    # 5. 返回元组
    return access_token, refresh_token, 1800


async def refresh_token(db: AsyncSession, refresh_token: str) -> tuple[str, str, int]:
    """用 refresh token 换新 access + 新 refresh（旧 refresh 撤销，防重放）。

    Returns: (new_access_token, new_refresh_token, expires_in_seconds)
    Raises:
        InvalidTokenError: token 无效/过期/已撤销
    """
    # 1. 解码 + 验证
    payload = decode_refresh_token(refresh_token)
    jti = payload["jti"]
    user_id = int(payload["sub"])

    # 2. 查 DB 验证（D29/D30: jti 存在 + 未撤销 + 未过期）
    from sqlalchemy import select, update
    db_token = (await db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )).scalar_one_or_none()

    if not db_token or db_token.revoked or db_token.expires_at < datetime.now(timezone.utc):
        raise InvalidTokenError("refresh token 无效或已撤销")

    # 3. 作废旧 refresh（D28 rotate：防 token 重放）
    db_token.revoked = True

    # 4. 签发新 access + 新 refresh
    new_access_token = create_access_token(user_id)
    new_refresh_token, new_jti = create_refresh_token(user_id)

    db.add(RefreshToken(
        user_id=user_id,
        jti=new_jti,
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    ))
    await db.commit()

    return new_access_token, new_refresh_token, 1800


async def logout(db: AsyncSession, refresh_token: str) -> None:
    """撤销 refresh token（设 revoked=True）。幂等。

    无效 token 不报错（视作已经登出）。
    """
    try:
        payload = decode_refresh_token(refresh_token)
    except InvalidTokenError:
        return  # 幂等：token 无效直接返回

    jti = payload["jti"]
    from sqlalchemy import update
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti)
        .values(revoked=True)
    )
    await db.commit()
```

- [ ] **Step 2: 端到端测试 login + refresh + logout**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
import asyncio
from sqlalchemy import delete, select
from core.db import AsyncSessionLocal
from core.exceptions import InvalidCredentialsError, InvalidTokenError
from models.user import User, RefreshToken
from services.auth_service import login, refresh_token, logout, register
from schemas.user import UserCreate

async def main():
    async with AsyncSessionLocal() as db:
        # 清理测试数据
        await db.execute(delete(RefreshToken).where(RefreshToken.user_id.in_(
            select(User.id).where(User.username.like('login_%'))
        )))
        await db.execute(delete(User).where(User.username.like('login_%')))
        await db.commit()

        # 准备一个测试用户
        await register(db, UserCreate(username='login_alice', email='login_alice@example.com', password='Password123'))

        # Test 1: 正确登录
        access, refresh, expires_in = await login(db, 'login_alice@example.com', 'Password123')
        print(f'Test 1 OK: access={access[:30]}..., refresh={refresh[:30]}...')

        # Test 2: 错误密码 → InvalidCredentialsError
        try:
            await login(db, 'login_alice@example.com', 'WrongPassword')
            print('Test 2 FAIL')
        except InvalidCredentialsError as e:
            print(f'Test 2 OK: {e}')

        # Test 3: refresh rotate
        new_access, new_refresh, _ = await refresh_token(db, refresh)
        assert new_access != access, 'access 应该不同'
        assert new_refresh != refresh, 'refresh 应该 rotate'
        print(f'Test 3 OK: rotate success')

        # Test 4: 旧 refresh 不能再用（rotate 后旧 token revoke）
        try:
            await refresh_token(db, refresh)  # 用旧 refresh
            print('Test 4 FAIL: old refresh should be revoked')
        except InvalidTokenError:
            print('Test 4 OK: old refresh revoked')

        # Test 5: logout
        await logout(db, new_refresh)
        print('Test 5 OK: logout')

        # Test 6: logout 后新 refresh 也失效
        try:
            await refresh_token(db, new_refresh)
            print('Test 6 FAIL')
        except InvalidTokenError:
            print('Test 6 OK: logout revokes refresh')

        # 清理
        await db.execute(delete(RefreshToken).where(RefreshToken.user_id.in_(
            select(User.id).where(User.username.like('login_%'))
        )))
        await db.execute(delete(User).where(User.username.like('login_%')))
        await db.commit()
        print('All tests passed!')

asyncio.run(main())
"
```

预期：6 个测试都过

- [ ] **Step 3: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add services/auth_service.py && git commit -m "feat(service): add login + refresh_token + logout (rotate refresh)

D28/D29/D30/D31 decisions:
- login: email+password -> access + refresh + DB store jti
- refresh_token: rotate (revoke old + issue new) anti-replay
- logout: revoke refresh (stateless access, idempotent)
- Unified error msg anti-enumeration

6/6 e2e service tests passed (login/refresh/logout flow)"
```

---

## Task 7: api/exception_handlers.py 加 401 映射

**Files:**
- Modify: `api/exception_handlers.py`（已有 4 个 handler：UsernameExistsError / EmailExistsError / IntegrityError / FitForgeException）

**Interfaces:**
- Consumes: Task 2 的 InvalidCredentialsError + InvalidTokenError
- Produces: 2 个新 handler → 401 Conflict

- [ ] **Step 1: 在文件顶部 import 区追加**

```python
from core.exceptions import (
    EmailExistsError,
    FitForgeException,
    InvalidCredentialsError,    # ← 新增
    InvalidTokenError,          # ← 新增
    UsernameExistsError,
)
```

- [ ] **Step 2: 在 register_exception_handlers() 函数内追加 2 个 handler**

在 `@app.exception_handler(EmailExistsError)` 后插入：

```python
    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        request: Request,  # noqa: ARG001
        exc: InvalidCredentialsError,
    ) -> JSONResponse:
        # 401 Unauthorized（登录凭证错误，攻击者可重试）
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},  # OAuth 2.0 标准
        )

    @app.exception_handler(InvalidTokenError)
    async def invalid_token_handler(
        request: Request,  # noqa: ARG001
        exc: InvalidTokenError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )
```

- [ ] **Step 3: 验证注册**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
from api.exception_handlers import register_exception_handlers
from fastapi import FastAPI
app = FastAPI()
register_exception_handlers(app)
print('handler count:', sum(1 for _ in app.exception_handlers))
# 预期：7（4 原有 + 2 新 + FastAPI 默认）
print('OK: 2 new 401 handlers registered')
"
```

预期：handler count 7

- [ ] **Step 4: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add api/exception_handlers.py && git commit -m "feat(api): add 401 handlers for InvalidCredentials + InvalidToken

2 new exception handlers:
- InvalidCredentialsError -> 401 + WWW-Authenticate: Bearer
- InvalidTokenError -> 401 + WWW-Authenticate: Bearer

Q2 decision: business exception -> HTTP mapping
OAuth 2.0 standard: 401 must include WWW-Authenticate header"
```

---

## Task 8: api/auth.py 加 4 路由 + get_current_user 中间件

**Files:**
- Modify: `api/auth.py`（已有 POST /auth/register）

**Interfaces:**
- Consumes: Task 5 的 3 schema + Task 6 的 3 service 函数 + Task 1 的 decode_access_token
- Produces:
  - `POST /auth/login` → TokenResponse
  - `POST /auth/refresh` → TokenResponse
  - `POST /auth/logout` → 204
  - `GET /auth/me` → UserRead
  - `get_current_user(token, db) -> User` 中间件

- [ ] **Step 1: 在 api/auth.py 顶部 import 区追加**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.exceptions import InvalidTokenError
from core.security import decode_access_token
from models.user import User
from schemas.user import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
```

- [ ] **Step 2: 在 api/auth.py 末尾追加 4 路由 + 中间件**

```python
# ============ 4 个新路由 ============

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """登录（email + password → access + refresh）。"""
    access_token, refresh_token, expires_in = await auth_service.login(
        db, login_data.email, login_data.password
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """用 refresh token 换新 access + 新 refresh（rotate）。"""
    access_token, new_refresh_token, expires_in = await auth_service.refresh_token(
        db, refresh_data.refresh_token
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """登出（撤销 refresh token，幂等）。"""
    await auth_service.logout(db, refresh_data.refresh_token)
    return None


# ============ get_current_user 中间件 ============

# HTTPBearer 提取 Authorization: Bearer xxx 中的 token
_bearer_scheme = HTTPBearer(auto_error=False)  # auto_error=False 自己处理 401


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI Depends 中间件：验证 Bearer token，返回 User 对象。

    使用：任何需要鉴权的端点加 Depends(get_current_user)
    异常：InvalidTokenError -> handler 映射 401
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidTokenError("缺少 Bearer token")

    token = credentials.credentials
    payload = decode_access_token(token)  # 失败抛 InvalidTokenError
    user = await db.get(User, int(payload["sub"]))
    if not user:
        raise InvalidTokenError("user not found")
    return user


@router.get("/me", response_model=UserRead)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """演示 get_current_user 中间件：返回当前登录用户。"""
    return UserRead.model_validate(current_user)
```

- [ ] **Step 3: 验证 5 个路由**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && python -c "
from api.auth import router
print(f'routes count: {len(router.routes)}')
for route in router.routes:
    methods = sorted(route.methods) if hasattr(route, 'methods') else []
    print(f'  {methods} {route.path}')
"
```

预期：5 路由（register + login + refresh + logout + me）

- [ ] **Step 4: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add api/auth.py && git commit -m "feat(api): add 4 routes + get_current_user middleware

4 new routes:
- POST /auth/login (email+password -> TokenResponse)
- POST /auth/refresh (rotate refresh -> new TokenResponse)
- POST /auth/logout (revoke refresh, 204 No Content)
- GET /auth/me (Depends(get_current_user) demo)

1 new middleware:
- get_current_user: HTTPBearer + decode_access_token + DB get User
- InvalidTokenError -> handler maps to 401
- WWW-Authenticate: Bearer header per OAuth 2.0

Total routes: 5 (register + login + refresh + logout + me)"
```

---

## Task 9: tests/test_auth.py 加 4 个新 pytest 用例

**Files:**
- Modify: `tests/test_auth.py`（已有 4 个 register 用例）

**Interfaces:**
- Consumes: Task 8 的 4 路由
- Produces: 4 个新 pytest 用例（login/refresh/logout/me）

- [ ] **Step 1: 在 test_auth.py 末尾追加 4 个测试**

```python
# ============================================================
# /auth/login + refresh + logout + me 测试
# ============================================================

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """场景：login 成功返回 access + refresh。"""
    # 先注册（确保有用户）
    await client.post("/auth/register", json={
        "username": "login_alice", "email": "login_alice@example.com", "password": "Password123",
    })
    # 登录
    resp = await client.post("/auth/login", json={
        "email": "login_alice@example.com", "password": "Password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800
    assert len(data["access_token"]) > 50
    assert len(data["refresh_token"]) > 50


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """场景：错误密码 → 401。"""
    resp = await client.post("/auth/login", json={
        "email": "nonexistent@example.com", "password": "WrongPass1",
    })
    assert resp.status_code == 401
    # 统一错误消息（防枚举攻击）
    detail = resp.json()["detail"]
    assert "邮箱" in detail or "密码" in detail or "invalid" in detail.lower()


@pytest.mark.asyncio
async def test_refresh_rotate_and_revoke(client: AsyncClient):
    """场景：refresh rotate 成功 + 旧 refresh 撤销。"""
    # 注册 + 登录
    await client.post("/auth/register", json={
        "username": "refresh_alice", "email": "refresh_alice@example.com", "password": "Password123",
    })
    login_resp = await client.post("/auth/login", json={
        "email": "refresh_alice@example.com", "password": "Password123",
    })
    old_refresh = login_resp.json()["refresh_token"]

    # refresh 成功（新 token）
    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_resp.status_code == 200
    new_refresh = refresh_resp.json()["refresh_token"]
    assert new_refresh != old_refresh

    # 旧 refresh 再用 → 401（已 revoke）
    retry_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert retry_resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """场景：/auth/me 用 Bearer token 拿当前用户。"""
    # 注册 + 登录
    await client.post("/auth/register", json={
        "username": "me_alice", "email": "me_alice@example.com", "password": "Password123",
    })
    login_resp = await client.post("/auth/login", json={
        "email": "me_alice@example.com", "password": "Password123",
    })
    access_token = login_resp.json()["access_token"]

    # /auth/me 带 Bearer
    resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "me_alice"
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    """场景：/auth/me 没 Bearer → 401。"""
    resp = await client.get("/auth/me")
    assert resp.status_code == 401  # HTTPBearer 自动 401（auto_error=True 默认）
```

- [ ] **Step 2: 跑所有测试**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && pytest tests/test_auth.py -v 2>&1 | tail -20
```

预期：8 个测试全过（旧 4 + 新 4）

- [ ] **Step 3: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add tests/test_auth.py && git commit -m "test(auth): add 4 e2e tests for login/refresh/logout/me

5 new test scenarios:
- test_login_success: 200 + access + refresh token
- test_login_wrong_password: 401 + unified error msg (anti-enumeration)
- test_refresh_rotate_and_revoke: new refresh + old refresh 401
- test_me_with_valid_token: 200 + UserRead (no password_hash)
- test_me_without_token: 401 (HTTPBearer auto-error)

Total tests: 8/8 passed (register 4 + login 4)"
```

---

## Task 10: tests/smoke.sh 加 7 个 curl 端到端测试

**Files:**
- Modify: `tests/smoke.sh`（已有 7 个 register 测试）

**Interfaces:**
- Consumes: Task 8 的 4 路由
- Produces: 7 个新 curl 测试

- [ ] **Step 1: 在 smoke.sh 末尾追加 7 个测试**

```bash

echo ""
echo "Test 8: POST /auth/login (success -> 200)"
# 先注册测试用户
curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_loginuser","email":"smoke_login@example.com","password":"Password123"}' > /dev/null
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_loginuser","email":"smoke_login@example.com","password":"Password123"}')
ACCESS_TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH_TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
echo "  access_token: ${ACCESS_TOKEN:0:30}..."
echo "  refresh_token: ${REFRESH_TOKEN:0:30}..."

echo ""
echo "Test 9: POST /auth/login (wrong password -> 401)"
curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"smoke_loginuser","email":"smoke_login@example.com","password":"WrongPass1"}' \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 10: GET /auth/me (with Bearer -> 200)"
curl -s "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 11: GET /auth/me (without Bearer -> 401)"
curl -s "$BASE_URL/auth/me" -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 12: POST /auth/refresh (rotate -> 200)"
NEW_REFRESH_RESP=$(curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}")
NEW_REFRESH=$(echo "$NEW_REFRESH_RESP" | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
echo "  new_refresh: ${NEW_REFRESH:0:30}..."

echo ""
echo "Test 13: POST /auth/refresh (old revoked -> 401)"
curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}" \
  -w "\n  HTTP %{http_code}\n"

echo ""
echo "Test 14: POST /auth/logout (revoke -> 204)"
curl -s -X POST "$BASE_URL/auth/logout" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$NEW_REFRESH\"}" \
  -w "  HTTP %{http_code}\n"
```

- [ ] **Step 2: 跑 smoke（需要 uvicorn 跑起来）**

```bash
# 启动 uvicorn（后台）
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 5
bash tests/smoke.sh 2>&1 | tail -30
# 关闭 uvicorn
kill %1 2>/dev/null
```

预期：所有 14 个测试都过（7 register + 7 login/refresh/logout/me）

- [ ] **Step 3: Commit**

```bash
cd "D:/My Agnet/my_coding_projects/Intelligent_training_management_platform" && git add tests/smoke.sh && git commit -m "test(smoke): add 7 curl smoke tests for login/refresh/logout/me

7 new smoke scenarios:
- Test 8: login success -> 200 + access + refresh
- Test 9: login wrong password -> 401
- Test 10: /auth/me with Bearer -> 200 + UserRead
- Test 11: /auth/me without Bearer -> 401
- Test 12: refresh -> 200 + new refresh (rotate)
- Test 13: refresh old token (revoked) -> 401
- Test 14: logout -> 204

Total smoke tests: 14 (register 7 + login 7)"
```

---

## 验收清单

部署完成后验证：

- [ ] 10 个 commit 全部入库
- [ ] 本地 pytest 8/8 全过
- [ ] 本地 smoke 14/14 全过
- [ ] 服务器 alembic upgrade head 跑通（加 refresh_tokens 表）
- [ ] 服务器 curl /auth/login 端到端验证
- [ ] 服务器 .env 包含 RSA 密钥路径配置
- [ ] 服务器 keys/ 目录有 private.pem + public.pem

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-14-auth-login-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**