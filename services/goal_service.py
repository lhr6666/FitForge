"""user_goals 业务逻辑。

Q1 决策：重型 service 模式
- 接 Pydantic schema（UserGoalCreate / UserGoalUpdate）
- 返回 ORM 对象（路由层负责 ORM → UserGoalRead 转换）
- 抛业务异常（GoalNotFoundError）

设计要点：
- service 层不依赖 FastAPI（Q1 决策）
- 事务：单条用 flush + commit
- 跨用户访问统一返回 404 防枚举（D38）
- 不实现 delete_goal（Q5 / D36 决策 —— goal 是历史轨迹，走 PATCH status=abandoned）
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import GoalNotFoundError
from models.user import User
from models.user_goal import UserGoal
from schemas.goal import UserGoalCreate, UserGoalUpdate


async def create_goal(
    db: AsyncSession,
    current_user: User,
    payload: UserGoalCreate,
) -> UserGoal:
    """创建目标（status 默认 active，Q5 决策：不允许创建时指定 status）。

    显式填 status="active" —— 即便 DB 列有 default，service 层也写明白，
    避免"DB 默认值 vs 应用层"语义不一致。
    """
    obj = UserGoal(
        user_id=current_user.id,
        status="active",
        **payload.model_dump(),
    )
    db.add(obj)
    await db.flush()
    await db.commit()
    return obj


async def list_goals(
    db: AsyncSession,
    current_user: User,
    *,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[UserGoal]:
    """列表（status 过滤 + 分页）。

    Q6 决策：limit <= 100 校验由路由层 FastAPI Query 负责。
    排序：created_at DESC（"最近创建"在前）。
    """
    stmt = (
        select(UserGoal)
        .where(UserGoal.user_id == current_user.id)
        .order_by(UserGoal.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(UserGoal.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_goal(
    db: AsyncSession,
    current_user: User,
    goal_id: int,
) -> UserGoal:
    """取单条（含权限校验）。

    D38 关键：跨用户访问也抛 NotFoundError（不抛 UnauthorizedAccessError）防枚举。
    W2 关键：db.get() 不会自动 404，必须显式 None check。
    """
    obj = await db.get(UserGoal, goal_id)
    if obj is None or obj.user_id != current_user.id:
        raise GoalNotFoundError(f"目标 {goal_id} 不存在")
    return obj


async def update_goal(
    db: AsyncSession,
    current_user: User,
    goal_id: int,
    update: UserGoalUpdate,
) -> UserGoal:
    """update 5 字段（Q4 决策：type / target_value / status / deadline / notes）。

    W4 关键：用 update.model_dump(exclude_unset=True) —— 仅取 schema 里显式传的字段。
    """
    obj = await get_goal(db, current_user, goal_id)  # 自动验权（D38）
    update_data = update.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj
