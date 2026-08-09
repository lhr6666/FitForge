"""AuthService - 认证业务逻辑（注册、登录、token 签发）。

Q1 决策：重型 service 模式
- 接 Pydantic schema（UserCreate）
- 返回 ORM 对象（路由层负责转 DTO）
- 抛业务异常（UsernameExistsError / EmailExistsError）

设计要点：业务可复用 —— CLI/脚本/队列都直接调 service.register()，
不需要 FastAPI 依赖。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import EmailExistsError, UsernameExistsError
from core.security import hash_password
from models.user import User
from schemas.user import UserCreate


async def register(db: AsyncSession, user_create: UserCreate) -> User:
    """注册新用户。

    业务流程：
        1. 查重 username（应用层 99% 拦截）
        2. 查重 email（应用层 99% 拦截）
        3. 密码哈希（Argon2id，cost=12）
        4. 创建 User ORM 对象
        5. flush() 取 id + commit() 持久化
        6. 返回 ORM 对象（路由层用 UserRead.model_validate 转 DTO）

    异常：
        - UsernameExistsError：username 已被占用（路由层 → 409）
        - EmailExistsError：email 已被注册（路由层 → 409）

    DB 层兜底：
        - 即使应用层 99% 拦截，并发场景仍可能触发 DB UNIQUE 约束
        - 路由层 catch IntegrityError → 409（业务异常没处理的高并发场景）

    Args:
        db: AsyncSession（路由层 Depends 注入）
        user_create: UserCreate schema（路由层 Pydantic 自动校验）

    Returns:
        User ORM 对象（含 id、created_at 等 DB 自动填的字段）
    """
    # ===== Step 1: 查重 username =====
    existing = await db.execute(
        select(User).where(User.username == user_create.username)
    )
    if existing.scalar_one_or_none():
        raise UsernameExistsError(
            f"用户名 '{user_create.username}' 已被占用"
        )

    # ===== Step 2: 查重 email =====
    existing = await db.execute(
        select(User).where(User.email == user_create.email)
    )
    if existing.scalar_one_or_none():
        raise EmailExistsError(
            f"邮箱 '{user_create.email}' 已被注册"
        )

    # ===== Step 3: 创建 User =====
    user = User(
        username=user_create.username,
        email=user_create.email,
        password_hash=hash_password(user_create.password),
        nickname=user_create.nickname,
    )

    # ===== Step 4: 持久化 =====
    db.add(user)
    await db.flush()  # 触发 INSERT，让 DB 自动填 id / created_at
    await db.commit()  # 提交事务（默认无显式 commit，session 关闭时也会 commit）

    return user