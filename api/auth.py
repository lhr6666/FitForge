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
from schemas.user import UserCreate, UserRead
from services import auth_service


router = APIRouter(
    prefix="/auth",
    tags=["auth"],  # OpenAPI 文档分组
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