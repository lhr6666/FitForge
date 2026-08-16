"""AuthService - 认证业务逻辑（注册、登录、token 签发）。
这样子分层架构思想依赖http的就只有路由层那一块了，其他的都是python代码，以后也可以复用这些逻辑

Q1 决策：重型 service 模式
- 接 Pydantic schema（UserCreate）
- 返回 ORM 对象（路由层负责转 DTO）
- 抛业务异常（UsernameExistsError / EmailExistsError）

设计要点：业务可复用 —— CLI/脚本/队列都直接调 service.register()，
不需要 FastAPI 依赖。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import (
    EmailExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    UsernameExistsError,
)
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from models.user import RefreshToken, User
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
        #抛出的是自定义异常不涉及http
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
    #自增id作用就是给这个新的数据发一个唯一标识符，同时在flush之后可以通过这个id来完成其他的关联操作。
    #比如新用户注册送会员，那么代码逻辑就是先注册再送，那么flush的作用就是可以在真正提交之前完成其他的关联操作。如果失败了那么会自动回滚到最前面，此时还没有commit所以没有存到数据库当中
    #比如送会员，然后再提交事务，这样就可以保证送会员的操作和注册操作是原子性的，不会出现送会员操作失败导致用户没有注册成功的情况。
    #同时如果后续开发当中添加完用户后续需要别的操作可以写到flush后面，测试成功了再commit。
    await db.commit()  # 提交事务（默认无显式 commit，session 关闭时也会 commit）

    return user


# ============ /auth/login + refresh + logout 新增 service 函数 ============

async def login(db: AsyncSession, email: str, password: str) -> tuple[str, str, int]:
    """验证 email + password → 签发 access + refresh。

    Returns: (access_token, refresh_token, expires_in_seconds)
    Raises:
        InvalidCredentialsError: 用户不存在 or 密码错（统一消息防枚举攻击）

    D31: 统一返回 "邮箱或密码错误" — 攻击者无法通过响应区分"用户不存在"和"密码错"
    """
    # 1. 查 user（按 email）
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()

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
    expires_at = datetime.utcnow() + timedelta(days=14)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
        )
    )
    await db.commit()

    # 5. 返回元组
    return access_token, refresh_token, 1800


async def refresh_token(db: AsyncSession, refresh_token: str) -> tuple[str, str, int]:
    """用 refresh token 换新 access + 新 refresh（旧 refresh 撤销，防重放）。

    Returns: (new_access_token, new_refresh_token, expires_in_seconds)
    Raises:
        InvalidTokenError: token 无效/过期/已撤销

    D28: refresh token rotate —— 每次 refresh 作废旧 refresh + 签发新 refresh
    """
    # 1. 解码 + 验证
    payload = decode_refresh_token(refresh_token)
    jti = payload["jti"]
    user_id = int(payload["sub"])

    # 2. 查 DB 验证（D29/D30: jti 存在 + 未撤销 + 未过期）
    db_token = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
    ).scalar_one_or_none()

    # 统一用 datetime.utcnow() (naive) 跟 MySQL DateTime 一致（避免 naive vs aware 报错）
    if (
        not db_token
        or db_token.revoked
        or db_token.expires_at < datetime.utcnow()
    ):
        raise InvalidTokenError("refresh token 无效或已撤销")

    # 3. 作废旧 refresh（D28 rotate：防 token 重放）
    db_token.revoked = True

    # 4. 签发新 access + 新 refresh
    new_access_token = create_access_token(user_id)
    new_refresh_token, new_jti = create_refresh_token(user_id)

    db.add(
        RefreshToken(
            user_id=user_id,
            jti=new_jti,
            expires_at=datetime.utcnow() + timedelta(days=14),
        )
    )
    await db.commit()

    return new_access_token, new_refresh_token, 1800


async def logout(db: AsyncSession, refresh_token: str) -> None:
    """撤销 refresh token（设 revoked=True）。幂等（多次操作结果一样）

    无效 token 不报错（视作已经登出）。eg：用户点了“退出”，网络卡了一下，用户又狂点了两下“退出”，难道给用户报错吗？
    """
    try:
        payload = decode_refresh_token(refresh_token)#这一步是用钥匙（公钥）解开看看是否正确
    except InvalidTokenError:
        return  # 幂等：token 无效直接返回

    jti = payload["jti"]#从 Token 的内容里，提取出它的唯一身份证号（JTI）
    await db.execute(
        update(RefreshToken) # 【1】目标：我要修改 refresh_tokens 这张表
        .where(RefreshToken.jti == jti) # 【2】筛选：找到 jti 等于刚才那个号码的记录
        .values(revoked=True)    # 【3】动作：把它的 revoked 字段改成 True（True=失效/作废）
    )
    await db.commit()#提交