# /auth/login + refresh + logout 设计文档

> **日期**：2026-08-14（周四）
> **作者**：LHR6666（与 Claude Code brainstorming 产出）
> **目的**：设计 /auth/login、refresh、logout 端点 + JWT 中间件
> **关联决策**：D5（PyJWT）、D7（RS256）、D19（6 决策）、D26（容器化）、D27（密码 lhr076200）
> **关联 spec**：`docs/superpowers/specs/2026-07-06-auth-register-design.md`（/auth/register 已完成）
> **状态**：⏳ 待用户 review

---

## 1. 概述

### 1.1 设计目标

实现 FitForge 完整认证系统的后半部分：
- **/auth/login**：email + password 验证 → 签发 access token + refresh token
- **/auth/refresh**：refresh token 换新 access token（**rotate** refresh 防重放）
- **/auth/logout**：撤销 refresh token（无状态 access，客户端删）
- **/auth/me**：演示 Depends(get_current_user) 中间件
- **get_current_user**：FastAPI Depends，验证 Bearer token，返回 User 对象

### 1.2 与 /auth/register 的关系

| 维度 | /auth/register | /auth/login |
|------|----------------|-------------|
| 输入 | username + email + password | email + password |
| 输出 | UserRead（id, username, nickname）| TokenResponse（access + refresh） |
| 业务异常 | UsernameExistsError / EmailExistsError | InvalidCredentialsError |
| 状态码 | 201 / 409 / 422 | 200 / 401 / 422 |

**架构复用**（register 的 6 决策全适用）：
- ✅ Q1 重型 service（接 schema、抛业务异常）
- ✅ Q2 业务异常体系（InvalidCredentialsError 继承 FitForgeException）
- ✅ Q3 Depends 注入 session（get_db + get_current_user）
- ✅ Q4 2 schema（LoginRequest + TokenResponse 不含 password_hash）
- ✅ Q5 中等密码强度（用 verify_password 不存明文）
- ✅ Q6 email 必填（LoginRequest 必须传 email）

---

## 2. 端点定义

### 2.1 POST /auth/login

**请求**：
```json
{
  "email": "alice@example.com",
  "password": "Password123"
}
```

**响应（200）**：
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**异常**：
- 422：Pydantic 校验失败（缺 email / 弱密码）
- 401：`InvalidCredentialsError`（统一消息防枚举）
- 500：未捕获异常

### 2.2 POST /auth/refresh

**请求**：
```json
{
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**响应（200）**：
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",  // 新
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",  // 新（rotate）
  "token_type": "bearer",
  "expires_in": 1800
}
```

**异常**：
- 422：Pydantic 校验失败（缺 refresh_token）
- 401：`InvalidTokenError`（签名错 / 过期 / 被撤销）

**关键行为**：每次 refresh 都会**作废旧 refresh + 签发新 refresh**——防 token 重放。

### 2.3 POST /auth/logout

**请求**：
```json
{
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**响应（204）**：无 body

**异常**：
- 422：缺 refresh_token
- 401：refresh_token 已经撤销（幂等：返回 204 也不报错）

### 2.4 GET /auth/me

**请求**：
```
GET /auth/me
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

**响应（200）**：
```json
{
  "id": 1,
  "username": "alice",
  "nickname": "Alice"
}
```

**异常**：
- 401：缺 Bearer / token 无效 / 过期 / 用户不存在
- 500：未捕获

---

## 3. 数据模型

### 3.1 新增 refresh_tokens 表

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    jti = Column(String(36), unique=True, nullable=False, index=True)  # UUID4
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user_active", "user_id", "revoked"),
    )
```

**字段说明**：
- `jti`（JWT ID）：uuid4 字符串，保证每个 refresh token 唯一
- `expires_at`：DB 端过期时间（与 token 内 exp 一致）
- `revoked`：是否被撤销（logout / rotate 时设为 True）

### 3.2 User 模型加关系

```python
class User(Base):
    # ... 已有字段 ...
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

---

## 4. 关键代码骨架

### 4.1 core/security.py 新增 JWT 函数

```python
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid
import jwt
from core.config import settings

# 启动时加载密钥（仅一次）
_PRIVATE_KEY: str = ""
PUBLIC_KEY: str = ""

def _load_keys() -> None:
    global PRIVATE_KEY, PUBLIC_KEY
    with open(settings.JWT_PRIVATE_KEY_PATH) as f:
        PRIVATE_KEY = f.read()
    with open(settings.JWT_PUBLIC_KEY_PATH) as f:
        PUBLIC_KEY = f.read()

def create_access_token(user_id: int) -> str:
    """签发 access token（30 分钟）。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user_id: int) -> tuple[str, str]:
    """签发 refresh token（14 天） + 返回 jti。"""
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=14)).timestamp()),
        "type": "refresh",
    }
    token = jwt.encode(payload, PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti

def decode_access_token(token: str) -> dict[str, Any]:
    """解码 + 验证 access token。失败抛 InvalidTokenError。"""
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("token 已过期")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("token 无效")
    if payload.get("type") != "access":
        raise InvalidTokenError("token 类型错误")
    return payload

def decode_refresh_token(token: str) -> dict[str, Any]:
    """解码 + 验证 refresh token。"""
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("refresh token 已过期")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("refresh token 无效")
    if payload.get("type") != "refresh":
        raise InvalidTokenError("token 类型错误")
    return payload
```

### 4.2 services/auth_service.py 新增 3 个函数

```python
from sqlalchemy import select, update
from core.security import (
    create_access_token, create_refresh_token,
    decode_refresh_token, decode_access_token, hash_password, verify_password
)
from models.user import User, RefreshToken
from core.exceptions import InvalidCredentialsError, InvalidTokenError


async def login(db: AsyncSession, email: str, password: str) -> tuple[str, str, int]:
    """验证 email+password，返回 (access_token, refresh_token, expires_in)。"""
    # 1. 找 user（按 email）
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        # 统一消息防枚举攻击
        raise InvalidCredentialsError("邮箱或密码错误")

    # 2. 验密码（Argon2id）
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("邮箱或密码错误")

    # 3. 签发 access + refresh
    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)

    # 4. refresh 写 DB
    expires_at = datetime.now(timezone.utc) + timedelta(days=14)
    db.add(RefreshToken(
        user_id=user.id,
        jti=jti,
        expires_at=expires_at,
    ))
    await db.commit()

    return access_token, refresh_token, 1800


async def refresh_token(db: AsyncSession, refresh_token: str) -> tuple[str, str, int]:
    """用 refresh token 换新 access + 新 refresh（旧 refresh 作废）。"""
    # 1. 解码 + 验证
    payload = decode_refresh_token(refresh_token)

    # 2. 查 DB（jti 是否存在 + 未撤销 + 未过期）
    jti = payload["jti"]
    db_token = (await db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )).scalar_one_or_none()
    if not db_token or db_token.revoked or db_token.expires_at < datetime.now(timezone.utc):
        raise InvalidTokenError("refresh token 无效或已撤销")

    # 3. 作废旧 refresh（防重放）
    db_token.revoked = True

    # 4. 签发新 access + 新 refresh
    user_id = int(payload["sub"])
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
    """撤销 refresh token（设 revoked=True）。幂等。"""
    try:
        payload = decode_refresh_token(refresh_token)
    except InvalidTokenError:
        return  # 幂等：无效 token 当作已经登出

    jti = payload["jti"]
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti)
        .values(revoked=True)
    )
    await db.commit()
```

### 4.3 api/auth.py 新增 4 个路由

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from core.exceptions import InvalidTokenError, FitForgeException
from core.security import decode_access_token
from models.user import User
from schemas.user import LoginRequest, RefreshRequest, TokenResponse
from services import auth_service


# ============ 新增 4 个路由 ============

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,  # Pydantic 自动校验
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
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
    access_token, new_refresh_token, expires_in = await auth_service.refresh_token(
        db, refresh_data.refresh_token
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/logout", status_code=204)
async def logout(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.logout(db, refresh_data.refresh_token)
    return None  # 204 无 body


# ============ get_current_user 中间件 ============

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials  # "Bearer xxx" 中的 "xxx"
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=str(e))
    user = await db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
```

### 4.4 schemas/user.py 新增 3 个 schema

```python
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒
```

---

## 5. 关键设计决策

### D28：双 token + refresh rotate 机制

**决策**：access 30 分钟 + refresh 14 天 + 每次 refresh rotate。

**理由**：
- 单 access token 寿命短 → 泄露风险低
- refresh rotate → 防 token 重放（窃取 refresh 也只能用一次）
- 业界标准（OAuth 2.0 RFC 6749 + 各大厂实践）

**为什么不单 access token（14 天）**：
- 长寿命 token 泄露风险高
- 撤销困难（无黑名单机制）

### D29：refresh token DB 存储 + jti

**决策**：refresh token 写 DB（jti + expires_at + revoked）

**理由**：
- 可以主动撤销（logout）
- 可以 rotate（防重放）
- 可以审计（用户登录历史）

**为什么不存 access token**：
- access 短寿命（30 分钟），过期自动失效
- DB 查 access 反而拖慢请求

### D30：refresh token revoke 而非 blacklist

**决策**：refresh 表 `revoked` 字段（boolean）记录撤销状态

**理由**：
- 单字段查询快（`WHERE jti=? AND revoked=false`）
- 比 Redis 黑名单简单（不引入新依赖）
- MVP 阶段够用

### D31：密码错误统一返回"邮箱或密码错误"

**决策**：用户不存在 + 密码错 都返回同一消息

**理由**：
- 防枚举攻击（攻击者不能通过响应区分"用户不存在"和"密码错"）
- 业界标准（GitHub / Google 都是这样）

---

## 6. 错误处理（6 异常 → 5 状态码）

| 异常 | HTTP 状态码 | 触发 |
|------|------------|------|
| Pydantic ValidationError | 422 | 缺 email / 弱密码 / 缺 refresh_token |
| `InvalidCredentialsError` | **401** | 邮箱不存在 / 密码错 |
| `InvalidTokenError` | **401** | token 签名错 / 过期 / 类型错 / 已撤销 |
| `RefreshTokenRevokedError` | 401 | refresh 已被 revoke |
| Exception（未捕获） | 500 | 后端 bug |

**401 vs 422**：
- 401 = 客户端身份问题（重试密码不行）
- 422 = 请求格式问题（修 input）

---

## 7. 测试策略

### 7.1 单元测试（pytest）

```python
# tests/test_auth.py 新增
async def test_login_success()
async def test_login_wrong_password()  → 401
async def test_login_email_not_found()  → 401（同样消息）
async def test_refresh_success()  → 新 access + 新 refresh
async def test_refresh_token_reuse()  → 401（旧 refresh 被 revoke）
async def test_logout_revokes_refresh()
async def test_get_current_user_valid_token()
async def test_get_current_user_invalid_token()  → 401
```

### 7.2 端到端测试（curl smoke）

```bash
# 7 个新场景
Test 5: login success → 200 + access + refresh
Test 6: login wrong password → 401
Test 7: refresh success → 200 + 新 token
Test 8: refresh with revoked token → 401
Test 9: logout → 204
Test 10: /auth/me with valid Bearer → 200 + UserRead
Test 11: /auth/me with no Bearer → 401
```

---

## 8. 风险点 + 防范策略

| 风险 | 影响 | 防范 |
|------|------|------|
| **refresh token 重放** | 窃取者无限换 access | rotate（旧 refresh 立刻 revoke，DB 验证 `revoked=false`） |
| **access token 泄露** | 30 分钟窗口 | HTTPS + 短寿命 + 客户端存内存（不存 localStorage） |
| **DB 容量膨胀** | refresh_tokens 表无限增长 | cron job 定期清理 `expires_at < now() AND revoked=true` |
| **refresh 表查询慢** | 10 万级 token 时性能差 | 索引 `idx_refresh_tokens_user_active (user_id, revoked)` |
| **枚举攻击** | 攻击者探测用户名 | 统一错误消息"邮箱或密码错误" |
| **jwt 密钥泄露** | 攻击者签任意 token | 私钥 chmod 600（D18 决策）+ 定期 rotate |

---

## 9. YAGNI（不做清单）

- ❌ /auth/forgot-password → 第 4 周
- ❌ /auth/reset-password → 第 4 周
- ❌ 2FA / MFA → 第 5 周
- ❌ OAuth 2.0 provider（Google/GitHub login） → 第 6 周
- ❌ Admin 强制登出端点 → 第 3 周
- ❌ refresh token family（防设备重放） → 第 3 周
- ❌ device tracking → 第 6 周

---

## 10. 关联文档

- /auth/register spec：`docs/superpowers/specs/2026-07-06-auth-register-design.md`
- 部署文档：`docs/deploy-to-server.md`
- Argon2id 沉淀：`tech_notes/2026-07-06-argon2id-password-hash.md`
- 业务异常沉淀：`tech_notes/2026-07-06-business-exceptions.md`

---

## 11. 8 commit 计划

1. `core/security.py` 加 create/decode JWT（4 个函数 + 密钥加载）
2. `core/exceptions.py` 加 InvalidCredentialsError + InvalidTokenError
3. `models/user.py` 加 RefreshToken 模型 + User 关系
4. `alembic revision --autogenerate` 创建 refresh_tokens 表 + `alembic upgrade head`
5. `schemas/user.py` 加 LoginRequest + RefreshRequest + TokenResponse
6. `services/auth_service.py` 加 login + refresh_token + logout
7. `api/exception_handlers.py` 加 401 映射（InvalidCredentialsError + InvalidTokenError）
8. `api/auth.py` 加 4 个路由（login/refresh/logout/me）+ Depends(get_current_user)

---

## 12. 审批与变更记录

| 日期 | 版本 | 变更 | 审批人 |
|------|------|------|--------|
| 2026-08-14 | v1 | 初稿：双 token + refresh rotate | LHR6666（待 review）|

---

**审批状态**：⏳ 待用户 review（confirm → writing-plans）