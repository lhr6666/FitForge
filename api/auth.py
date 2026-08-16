"""认证路由层 - /auth/register 等端点。

Q3 决策：async generator + Depends 注入 AsyncSession
Q4 决策：ORM → DTO 转换（路由层做，不污染 service 层）

设计原则：
- 路由层只做 HTTP 适配（解析 body、调 service、ORM → DTO 转换）
- 业务逻辑在 service 层（auth_service.register）
- 异常映射在 api/exception_handlers.py
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.security import get_current_user
from models.user import User
from schemas.user import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from services import auth_service


router = APIRouter(
    prefix="/auth",#在该模块下面的全部路由前端都自带这个前缀防止重复手写
    tags=["auth"],  # OpenAPI 自动分组（Swagger UI 显示 "auth" 标签页）也就是把该模块归类到“auth”的标签内便于查找
)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="Q4: 极简响应体（不含 password_hash），Q6: email 必填，Q5: 密码强度校验",
)
async def register(
    user_create: UserCreate,  # Pydantic 自动校验（422 if fail）
    db: AsyncSession = Depends(get_db),  # Q3: session 与 HTTP 请求绑定
) -> UserRead:
    """用户注册端点。

    业务流程（详见 services/auth_service.register）：
        1. Pydantic 自动校验 UserCreate（422 if fail）
        2. service 层查重 + 哈希密码 + 创建 user
        3. 路由层 ORM → UserRead 转换（无 password_hash）
        4. 业务异常自动映射：UsernameExistsError → 409 等

    Returns:
        UserRead：id / username / nickname（无 password_hash）

    Raises（自动映射）：
        - 422：Pydantic 校验失败
        - 409：username/email 重复（含 DB UNIQUE 兜底）
        - 500：未捕获异常
    """
    user = await auth_service.register(db, user_create)
    return UserRead.model_validate(user)


# ============ /auth/login + refresh + logout + me 新增路由 ============

@router.post("/login", response_model=TokenResponse)
#路由层看到（前端/浏览器）：发起请求 POST /auth/login走这个函数
async def login(
    login_data: LoginRequest,#自动接收并解析 JSON 请求体
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """登录（email + password → access + refresh）。"""
    #跳转到 services/auth_service.py 去执行
    access_token, refresh_token, expires_in = await auth_service.login(
        db, login_data.email, login_data.password#传入login_data: LoginRequest这一行获取到的数据
    )
    #将生成的 Token 包装成 JSON 返回。
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",# 告诉前端这是 Bearer 类型的 Token
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


# ============ get_current_user 中间件（D39 决策：迁移到 core/security.py） ============


@router.get("/me", response_model=UserRead)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """演示 get_current_user 中间件：返回当前登录用户。"""
    return UserRead.model_validate(current_user)