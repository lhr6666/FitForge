"""user_goals 路由层 - 4 端点。

Q1 决策：路由层只做 HTTP 适配 + ORM → DTO 转换
Q5 决策：不实现 DELETE（goal 是历史轨迹，走 PATCH status=abandoned）
D35: PATCH 允许全 5 字段（schema 已设 extra="forbid"，路由层不重复校验）
D37: limit ≤ 100 / offset ≥ 0 由 FastAPI Query 自动校验
D38: 跨用户访问统一返回 404（service 层已抛 GoalNotFoundError）
D39: get_current_user 从 core.security 注入
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.security import get_current_user
from models.user import User
from schemas.goal import UserGoalCreate, UserGoalRead, UserGoalUpdate
from services import goal_service


router = APIRouter(prefix="/user-goals", tags=["user-goals"])


@router.post(
    "",
    response_model=UserGoalRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_goal(
    payload: UserGoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserGoalRead:
    """POST /user-goals —— 创建目标（status 默认 active）。"""
    obj = await goal_service.create_goal(db, current_user, payload)
    return UserGoalRead.model_validate(obj)


@router.get("", response_model=list[UserGoalRead])
async def list_goals(
    status_param: Literal["active", "completed", "abandoned"] | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserGoalRead]:
    """GET /user-goals —— 列表（query: status/limit/offset）。

    status 参数 alias 为 'status'，但 Python 函数体里用 status_param 避免遮蔽 import。
    """
    objs = await goal_service.list_goals(
        db, current_user, status=status_param, limit=limit, offset=offset,
    )
    return [UserGoalRead.model_validate(o) for o in objs]


@router.get("/{goal_id}", response_model=UserGoalRead)
async def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserGoalRead:
    """GET /user-goals/{id} —— 取单条（含权限校验）。"""
    obj = await goal_service.get_goal(db, current_user, goal_id)
    return UserGoalRead.model_validate(obj)


@router.patch("/{goal_id}", response_model=UserGoalRead)
async def update_goal(
    goal_id: int,
    update: UserGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserGoalRead:
    """PATCH /user-goals/{id} —— update 5 字段（type/target_value/status/deadline/notes）。"""
    obj = await goal_service.update_goal(db, current_user, goal_id, update)
    return UserGoalRead.model_validate(obj)
