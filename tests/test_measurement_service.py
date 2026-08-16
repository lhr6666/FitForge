"""body_measurements service 单元测试。

覆盖 6 个 service 函数的 200/404 路径（D38 防枚举 + W2/W4/W5 关键点）。
共 9 个核心 case。

fixtures: conftest.py 提供 db_session + sample_user（autouse clean_test_data 隔离）
"""

from datetime import datetime, timedelta

import pytest

from core.exceptions import MeasurementNotFoundError
from models.user import User
from schemas.measurement import (
    BodyMeasurementBatchCreate,
    BodyMeasurementCreate,
    BodyMeasurementPatch,
)
from services.measurement_service import (
    create_measurement,
    create_measurements_batch,
    delete_measurement,
    get_measurement,
    list_measurements,
    patch_measurement,
)


@pytest.mark.asyncio
async def test_create_measurement_ok(db_session, sample_user):
    """create_measurement: 单条创建成功 + 自动填 id/user_id。"""
    payload = BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow())
    obj = await create_measurement(db_session, sample_user, payload)
    assert obj.id is not None
    assert obj.user_id == sample_user.id
    assert obj.weight == 70.0


@pytest.mark.asyncio
async def test_create_measurements_batch_all_or_nothing(db_session, sample_user):
    """create_measurements_batch: 批量创建成功（W5 整体事务）。"""
    valid_time = datetime.utcnow()
    payload = BodyMeasurementBatchCreate(items=[
        BodyMeasurementCreate(weight=70.0, recorded_at=valid_time),
        BodyMeasurementCreate(weight=71.0, recorded_at=valid_time),
    ])
    objs = await create_measurements_batch(db_session, sample_user, payload)
    assert len(objs) == 2
    # 验证全部入库
    all_list = await list_measurements(db_session, sample_user)
    assert len(all_list) == 2


@pytest.mark.asyncio
async def test_list_measurements_default(db_session, sample_user):
    """list_measurements: 默认参数（无 date_from/to）+ 全部返回。"""
    now = datetime.utcnow()
    for w in [70.0, 71.0, 72.0]:
        await create_measurement(
            db_session, sample_user,
            BodyMeasurementCreate(weight=w, recorded_at=now),
        )
    result = await list_measurements(db_session, sample_user)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_list_measurements_with_date_range(db_session, sample_user):
    """list_measurements: date_from 过滤生效（早于基准的 1 条应被滤掉）。"""
    base = datetime.utcnow()
    await create_measurement(
        db_session, sample_user,
        BodyMeasurementCreate(weight=70.0, recorded_at=base - timedelta(days=10)),
    )
    await create_measurement(
        db_session, sample_user,
        BodyMeasurementCreate(weight=71.0, recorded_at=base),
    )
    result = await list_measurements(
        db_session, sample_user,
        date_from=base - timedelta(days=5),
    )
    assert len(result) == 1
    assert result[0].weight == 71.0


@pytest.mark.asyncio
async def test_get_measurement_ok(db_session, sample_user):
    """get_measurement: 本人可正常读取。"""
    obj = await create_measurement(
        db_session, sample_user,
        BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()),
    )
    got = await get_measurement(db_session, sample_user, obj.id)
    assert got.id == obj.id
    assert got.weight == 70.0


@pytest.mark.asyncio
async def test_get_measurement_not_found(db_session, sample_user):
    """get_measurement: id 不存在 -> MeasurementNotFoundError。"""
    with pytest.raises(MeasurementNotFoundError):
        await get_measurement(db_session, sample_user, 99999)


@pytest.mark.asyncio
async def test_get_measurement_other_user_returns_404(db_session, sample_user):
    """get_measurement: 跨用户访问 -> 404 防枚举（D38）。

    关键：故意抛 NotFoundError 而非 UnauthorizedAccessError（403），
    攻击者无法通过响应差异探测哪些 id 存在。
    """
    other = User(
        username="other_user",
        email="other@example.com",
        password_hash="x",
    )
    db_session.add(other)
    await db_session.commit()

    obj = await create_measurement(
        db_session, sample_user,
        BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()),
    )
    with pytest.raises(MeasurementNotFoundError):
        await get_measurement(db_session, other, obj.id)


@pytest.mark.asyncio
async def test_patch_measurement_notes_and_recorded_at(db_session, sample_user):
    """patch_measurement: 仅允许改 notes + recorded_at（Q3 / W3 / W4）。

    weight 不变（即使传入也不应被修改 —— 实际上 PATCH schema 拒 weight）。
    """
    obj = await create_measurement(
        db_session, sample_user,
        BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()),
    )
    new_time = datetime.utcnow() + timedelta(days=1)
    patched = await patch_measurement(
        db_session, sample_user, obj.id,
        BodyMeasurementPatch(notes="updated", recorded_at=new_time),
    )
    assert patched.notes == "updated"
    assert patched.weight == 70.0  # weight 不变


@pytest.mark.asyncio
async def test_delete_measurement_ok(db_session, sample_user):
    """delete_measurement: 硬删成功（再 get 应 NotFound）。"""
    obj = await create_measurement(
        db_session, sample_user,
        BodyMeasurementCreate(weight=70.0, recorded_at=datetime.utcnow()),
    )
    await delete_measurement(db_session, sample_user, obj.id)
    with pytest.raises(MeasurementNotFoundError):
        await get_measurement(db_session, sample_user, obj.id)