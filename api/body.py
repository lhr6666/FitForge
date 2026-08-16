"""body_measurements 路由层 - 6 端点。

Q1 决策：路由层只做 HTTP 适配（解析 body / query、ORM → DTO 转换）
Q3 决策：PATCH 仅允许 notes + recorded_at（W3: schema 已设 extra="forbid"，路由层不重复校验）
D33: 双端点（POST 单 / POST batch） + 整体事务
D37: limit ≤ 100 / offset ≥ 0 由 FastAPI Query 自动校验（422）
D38: 跨用户访问统一返回 404（service 层已抛 MeasurementNotFoundError）
D39: get_current_user 从 core.security 注入（避免循环 import）
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.security import get_current_user
from models.user import User
from schemas.measurement import (
    BodyMeasurementBatchCreate,
    BodyMeasurementBatchRead,
    BodyMeasurementCreate,
    BodyMeasurementPatch,
    BodyMeasurementRead,
)
from services import measurement_service


router = APIRouter(prefix="/body-measurements", tags=["body-measurements"])


@router.post(
    "",
    response_model=BodyMeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement(
    payload: BodyMeasurementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementRead:
    """POST /body-measurements —— 创建单条测量记录（201）。"""
    obj = await measurement_service.create_measurement(db, current_user, payload)
    return BodyMeasurementRead.model_validate(obj)


@router.post(
    "/batch",
    response_model=BodyMeasurementBatchRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurements_batch(
    payload: BodyMeasurementBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementBatchRead:
    """POST /body-measurements/batch —— 批量创建（整体事务）。"""
    objs = await measurement_service.create_measurements_batch(db, current_user, payload)
    return BodyMeasurementBatchRead(
        count=len(objs),
        items=[BodyMeasurementRead.model_validate(o) for o in objs],
    )


@router.get("", response_model=list[BodyMeasurementRead])
async def list_measurements(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BodyMeasurementRead]:
    """GET /body-measurements —— 列表（query: from/to/limit/offset）。"""
    objs = await measurement_service.list_measurements(
        db, current_user, date_from=from_, date_to=to, limit=limit, offset=offset,
    )
    return [BodyMeasurementRead.model_validate(o) for o in objs]


@router.get("/{measurement_id}", response_model=BodyMeasurementRead)
async def get_measurement(
    measurement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementRead:
    """GET /body-measurements/{id} —— 取单条（含权限校验）。"""
    obj = await measurement_service.get_measurement(db, current_user, measurement_id)
    return BodyMeasurementRead.model_validate(obj)


@router.patch("/{measurement_id}", response_model=BodyMeasurementRead)
async def patch_measurement(
    measurement_id: int,
    patch: BodyMeasurementPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BodyMeasurementRead:
    """PATCH /body-measurements/{id} —— 部分 update（仅 notes / recorded_at）。"""
    obj = await measurement_service.patch_measurement(db, current_user, measurement_id, patch)
    return BodyMeasurementRead.model_validate(obj)


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement(
    measurement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """DELETE /body-measurements/{id} —— 硬删（204 No Content）。"""
    await measurement_service.delete_measurement(db, current_user, measurement_id)
