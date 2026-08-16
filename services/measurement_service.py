"""body_measurements 业务逻辑。

Q1 决策：重型 service 模式
- 接 Pydantic schema（BodyMeasurementCreate / BatchCreate / Patch）
- 返回 ORM 对象（路由层负责 ORM → BodyMeasurementRead 转换）
- 抛业务异常（MeasurementNotFoundError）

设计要点：
- service 层不依赖 FastAPI（Q1 决策）—— 接 current_user: User ORM 而非 token str
- 事务边界：单条用 flush + commit；批量用 add_all + flush + commit（W5）
- 跨用户访问统一返回 404 防枚举（D38，W2 + W4 关键点见注释）
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import MeasurementNotFoundError
from models.body_measurement import BodyMeasurement
from models.user import User
from schemas.measurement import (
    BodyMeasurementBatchCreate,
    BodyMeasurementCreate,
    BodyMeasurementPatch,
)


async def create_measurement(
    db: AsyncSession,
    current_user: User,
    payload: BodyMeasurementCreate,
) -> BodyMeasurement:
    """创建单条测量记录。

    W5：单条事务用 flush + commit。
    """
    obj = BodyMeasurement(user_id=current_user.id, **payload.model_dump())
    db.add(obj)
    await db.flush()
    await db.commit()
    return obj


async def create_measurements_batch(
    db: AsyncSession,
    current_user: User,
    payload: BodyMeasurementBatchCreate,
) -> list[BodyMeasurement]:
    """批量创建（整体事务，W5）。

    任一 item 校验失败/flush 抛错 → 整个批次回滚（依赖 get_db 的 finally 兜底）。
    """
    objs = [
        BodyMeasurement(user_id=current_user.id, **item.model_dump())
        for item in payload.items
    ]
    db.add_all(objs)
    await db.flush()
    await db.commit()
    return objs


async def list_measurements(
    db: AsyncSession,
    current_user: User,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[BodyMeasurement]:
    """列表（按用户 + 时间区间 + limit/offset）。

    Q6 决策：limit <= 100 校验由路由层 FastAPI Query 负责；service 不重复校验。
    排序：recorded_at DESC（"最近测量"在前）。
    """
    stmt = (
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.recorded_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if date_from is not None:
        stmt = stmt.where(BodyMeasurement.recorded_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(BodyMeasurement.recorded_at <= date_to)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_measurement(
    db: AsyncSession,
    current_user: User,
    measurement_id: int,
) -> BodyMeasurement:
    """取单条（含权限校验：仅本人可读）。

    W2 关键：db.get() 不会自动 404，必须显式 None check。
    D38 关键：跨用户访问也抛 NotFoundError（不抛 UnauthorizedAccessError），
    防 ID 枚举攻击 —— 攻击者无法通过 403 vs 404 响应差异探测哪些 id 存在。
    """
    obj = await db.get(BodyMeasurement, measurement_id)
    if obj is None or obj.user_id != current_user.id:
        raise MeasurementNotFoundError(f"测量记录 {measurement_id} 不存在")
    return obj


async def patch_measurement(
    db: AsyncSession,
    current_user: User,
    measurement_id: int,
    patch: BodyMeasurementPatch,
) -> BodyMeasurement:
    """部分 update（仅允许 notes + recorded_at，Q3 决策）。

    W4 关键：用 patch.model_dump(exclude_unset=True) —— 仅取 schema 里显式传的字段，
    避免 None 值误清空已有字段。
    """
    obj = await get_measurement(db, current_user, measurement_id)  # 自动验权（D38）
    update_data = patch.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_measurement(
    db: AsyncSession,
    current_user: User,
    measurement_id: int,
) -> None:
    """硬删（含权限校验）。"""
    obj = await get_measurement(db, current_user, measurement_id)
    await db.delete(obj)
    await db.commit()
